import abc
import sys
import logging
from datetime import datetime
import argparse
from fn import _
from opentuner.resultsdb.models import *
from plugin import SearchPlugin

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--technique', action='append',
                       help="which technique to use")
argparser.add_argument('--list-techniques', action='store_true',
                       help="list techniques available and exit")

class SearchTechniqueBase(object):
  '''
  abstract base class for search techniques, with minimal interface
  '''
  __metaclass__ = abc.ABCMeta

  def is_ready(self):
    '''test if enough data has been gathered to use this technique'''
    return True

  @property
  def name(self):
    '''name of this SearchTechnique uses for display/accounting'''
    return self.__class__.__name__

  def handle_requested_result(self, result):
    '''called for each new Result(), requested by this technique'''
    pass

  @abc.abstractmethod
  def set_driver(self, driver):
    '''called at start of tuning process'''
    return

  @abc.abstractmethod
  def desired_result(self):
    '''
    return at most count resultsdb.models.DesiredResult objects based on past
    performance
    '''
    return

class SearchTechnique(SearchPlugin, SearchTechniqueBase):
  '''
  a search search technique with basic utility functions
  '''

  def __init__(self):
    super(SearchTechnique, self).__init__()
    self.driver      = None
    self.manipulator = None
    self.objective   = None

  def set_driver(self, driver):
    super(SearchTechnique, self).set_driver(driver)
    self.manipulator = driver.manipulator
    self.objective   = driver.objective
    driver.add_plugin(self)

  def desired_result(self):
    '''create and return a resultsdb.models.DesiredResult'''
    cfg = self.desired_configuration()
    if cfg is None:
      return None
    if type(cfg) is Configuration:
      config = cfg
    else:
      config = self.driver.get_configuration(cfg)
    desired = DesiredResult(
                  configuration = config,
                  requestor     = self.name,
                  generation    = self.driver.generation,
                  request_date  = datetime.now(),
                  tuning_run    = self.driver.tuning_run,
                )
    if hasattr(self, 'limit'):
      desired.limit = self.limit
    self.driver.register_result_callback(desired, self.handle_requested_result)
    return desired

  @abc.abstractmethod
  def desired_configuration(self):
    '''
    return a cfg that we should test
    given a ConfigurationManipulator and SearchDriver
    '''
    return dict()

  def handle_requested_result(self, result):
    '''called for each new Result(), regardless of who requested it'''
    pass

class MetaSearchTechnique(SearchTechniqueBase):
  '''
  a technique made up of a collection of other techniques
  '''
  def __init__(self, techniques):
    super(MetaSearchTechnique, self).__init__()
    self.techniques = techniques

  def set_driver(self, driver):
    super(MetaSearchTechnique, self).set_driver(driver)
    for t in self.techniques:
      t.set_driver(driver)
    self.driver = driver

  def desired_result(self):
    return self.select_technique().desired_result()

  @abc.abstractmethod
  def select_technique(self):
    '''select the next technique to use'''
    pass

class RoundRobinMetaSearchTechnique(MetaSearchTechnique):
  '''evenly switch between all source techniques'''
  def __init__(self, techniques):
    super(RoundRobinMetaSearchTechnique, self).__init__(techniques)
    self.idx = 0

  def select_technique(self):
    i = self.idx
    self.idx = (i+1) % len(self.techniques)
    return self.techniques[i]

class PureRandom(SearchTechnique):
  '''
  request configurations completely randomly
  '''
  def desired_configuration(self):
    return self.manipulator.random()

class AsyncProceduralSearchTechnique(SearchTechnique):
  def __init__(self):
    self.gen = None
    self.done = False
    self.latest_results = []
    super(AsyncProceduralSearchTechnique, self).__init__()

  def call_main_generator(self):
    '''passthrough (used in subclasses)'''
    return self.main_generator()

  def desired_configuration(self):
    if self.gen is None:
      self.gen = self.call_main_generator()
    if not self.done:
      try:
        return self.gen.next()
      except StopIteration:
        self.done = True
    return None

  @abc.abstractmethod
  def main_generator(self):
    '''
    custom generator to conduct this search, should:
    yield config
    to request tests and call driver.get_results() to read the results

    in AsyncProceduralSearchTechnique results are ready at an undefined
    time (`yield None` to stall and wait for them)

    in SequentialSearchTechnique results are ready after the yield
    '''
    pass

  def is_ready(self):
    return not self.done

class SequentialSearchTechnique(AsyncProceduralSearchTechnique):
  def __init__(self):
    self.pending_tests = []
    super(SequentialSearchTechnique, self).__init__()

  def yield_nonblocking(self, cfg):
    '''
    within self.main_generator() act like `yield cfg`, but don't wait for the
    results until the following yield (spawn/sync style)
    '''
    if cfg:
      self.pending_tests.append(cfg)

  def call_main_generator(self):
    '''insert waits for results after every yielded item'''
    subgen = self.main_generator()
    while True:
      try:
        p = subgen.next()
        if p:
          self.pending_tests.append(p)
      except StopIteration:
        return
      finally:
        for p in self.pending_tests:
          if not self.driver.has_results(p):
            yield p

      # wait for all pending_tests to have results
      while self.pending_tests:
        self.pending_tests = filter(lambda x: not self.driver.has_results(x),
                                    self.pending_tests)
        if self.pending_tests:
          yield None # wait


def all_techniques(args):
  import evolutionarytechniques
  import differentialevolution
  import simplextechniques
  return [
     PureRandom(),
     evolutionarytechniques.GreedyMutation(),
     simplextechniques.RandomTorczon(),
     simplextechniques.RandomNelderMead(),
     simplextechniques.RegularNelderMead(),
     simplextechniques.RightNelderMead(),
     simplextechniques.RandomTorczon(),
     simplextechniques.RegularTorczon(),
     simplextechniques.RightTorczon(),
     differentialevolution.DifferentialEvolution(),
     differentialevolution.DifferentialEvolutionAlt(),
    ]

def get_enabled(args):
  techniques = all_techniques(args)
  if args.list_techniques:
    for t in techniques:
      print t.name
    sys.exit(0)

  if not args.technique:
    args.technique = ['DifferentialEvolution',
                      'RightTorczon',
                      'GreedyMutation',
                      'RightTorczon']

  for unknown in set(args.technique) - set(map(_.name, techniques)):
    log.error("unknown technique %s", unknown)

  return [t for t in techniques if t.name in args.technique]

def get_root(args):
  from bandittechniques import AUCBanditMetaTechnique
  #RoundRobinMetaSearchTechnique
  return AUCBanditMetaTechnique(get_enabled(args))

