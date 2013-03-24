import abc
import sys
import logging
import argparse
from fn import _
from opentuner.resultsdb.models import *

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

  def is_ready(self, driver, generation):
    '''test if enough data has been gathered to use this technique'''
    return True

  @property
  def name(self):
    '''name of this SearchTechnique uses for display/accounting'''
    return self.__class__.__name__

  @property
  def priority(self):
    '''control order the technique gets run in, lower runs first'''
    return 0
  
  def handle_nonrequested_result(self, result, driver):
    '''called for each new Result(), requested by other techniques'''
    pass

  @abc.abstractmethod
  def desired_results(self, manipulator, driver, count):
    '''
    return at most count resultsdb.models.DesiredResult objects based on past
    performance
    '''
    return

  @abc.abstractmethod
  def handle_result(self, result, driver):
    '''called for each new Result(), requested'''
    pass




class SearchTechnique(SearchTechniqueBase):
  '''
  a search search technique with basic utility functions
  '''
  def desired_results(self, manipulator, driver, count):
    '''call search_suggestion() count times'''
    return filter(lambda x: x is not None,
                  [self.desired_result(manipulator, driver) for i in xrange(count)])

  def desired_result(self, manipulator, driver):
    '''create and return a resultsdb.models.DesiredResult'''
    cfg = self.desired_configuration(manipulator, driver)
    if cfg is None:
      return None
    if type(cfg) is Configuration:
      config = cfg
    else:
      config = driver.get_configuration(cfg)
    desired = DesiredResult()
    desired.configuration = config
    desired.priority_raw  = 1.0
    if hasattr(self, 'limit'):
      desired.limit = self.limit
    return desired

  @abc.abstractmethod
  def desired_configuration(self, manipulator, driver):
    '''
    return a cfg that we should test
    given a ConfigurationManipulator and SearchDriver
    '''
    return dict()

  def handle_result(self, result, driver):
    '''called for each new Result(), regardless of who requested it'''
    pass

class PureRandom(SearchTechnique):
  '''
  request configurations completely randomly
  '''
  def desired_configuration(self, manipulator, driver):
    return manipulator.random()

class AsyncProceduralSearchTechnique(SearchTechnique):
  def __init__(self):
    self.gen = None
    self.done = False
    self.latest_results = []
    super(AsyncProceduralSearchTechnique, self).__init__()

  def call_main_generator(self, manipulator, driver):
    '''passthrough (used in subclasses)'''
    return self.main_generator(manipulator, driver)

  def desired_configuration(self, manipulator, driver):
    if self.gen is None:
      self.gen = self.call_main_generator(manipulator, driver)
    if not self.done:
      try:
        return self.gen.next()
      except StopIteration:
        self.done = True
    return None

  @abc.abstractmethod
  def main_generator(self, manipulator, driver):
    '''
    custom generator to conduct this search, should:
    yield config
    to request tests and call driver.get_results() to read the results

    in AsyncProceduralSearchTechnique results are ready at an undefined
    time (`yield None` to stall and wait for them)

    in SequentialSearchTechnique results are ready after the yield
    '''
    pass

  def is_ready(self, driver, generation):
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

  def call_main_generator(self, manipulator, driver):
    '''insert waits for results after every yielded item'''
    subgen = self.main_generator(manipulator, driver)
    while True:
      try:
        p = subgen.next()
        if p:
          self.pending_tests.append(p)
      except StopIteration:
        return
      finally:
        for p in self.pending_tests:
          if not driver.has_results(p):
            yield p

      # wait for all pending_tests to have results
      while self.pending_tests:
        self.pending_tests = filter(lambda x: not driver.has_results(x),
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
    ]

def get_enabled(args):
  techniques = all_techniques(args)
  if args.list_techniques:
    for t in techniques:
      print t.name
    sys.exit(0)

  if not args.technique:
    args.technique = ['DifferentialEvolution']

  for unknown in set(args.technique) - set(map(_.name, techniques)):
    log.error("unknown technique %s", unknown)

  return [t for t in techniques if t.name in args.technique]

