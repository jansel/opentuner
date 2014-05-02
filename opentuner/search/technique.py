import abc
import sys
import os
import logging
from importlib import import_module
from datetime import datetime
import argparse
from fn import _
from opentuner.resultsdb.models import *
from plugin import SearchPlugin

log = logging.getLogger(__name__)
#log.setLevel(logging.DEBUG)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--technique','-t', action='append',
                       help="which technique to use")
argparser.add_argument('--list-techniques','-lt', action='store_true',
                       help="list techniques available and exit")

class SearchTechniqueBase(object):
  """
  abstract base class for search techniques, with minimal interface
  """
  __metaclass__ = abc.ABCMeta

  def __init__(self, name = None):
    super(SearchTechniqueBase, self).__init__()
    if name:
      self.name = name
    else:
      self.name = self.default_name()

  def is_ready(self):
    """test if enough data has been gathered to use this technique"""
    return True

  def default_name(self):
    """name of this SearchTechnique uses for display/accounting"""
    return self.__class__.__name__

  def handle_requested_result(self, result):
    """called for each new Result(), requested by this technique"""
    pass

  @abc.abstractmethod
  def set_driver(self, driver):
    """called at start of tuning process"""
    return

  @abc.abstractmethod
  def desired_result(self):
    """
    return at most count resultsdb.models.DesiredResult objects based on past
    performance
    """
    return

class SearchTechnique(SearchPlugin, SearchTechniqueBase):
  """
  a search search technique with basic utility functions
  """

  def __init__(self, *pargs, **kwargs):
    super(SearchTechnique, self).__init__(*pargs, **kwargs)
    self.driver = None
    self.manipulator = None
    self.objective = None
    self.request_count = 0

  def set_driver(self, driver):
    super(SearchTechnique, self).set_driver(driver)
    self.manipulator = driver.manipulator
    self.objective = driver.objective
    driver.add_plugin(self)

  def desired_result(self):
    """create and return a resultsdb.models.DesiredResult"""
    cfg = self.desired_configuration()
    if cfg is None:
      return None
    if type(cfg) is Configuration:
      config = cfg
    else:
      config = self.driver.get_configuration(cfg)
    desired = DesiredResult(configuration=config,
                            requestor=self.name,
                            generation=self.driver.generation,
                            request_date=datetime.now(),
                            tuning_run=self.driver.tuning_run)
    if hasattr(self, 'limit'):
      desired.limit = self.limit
    self.driver.register_result_callback(desired, self.handle_requested_result)
    self.request_count += 1
    return desired

  @abc.abstractmethod
  def desired_configuration(self):
    """
    return a cfg that we should test
    given a ConfigurationManipulator and SearchDriver
    """
    return dict()

  def handle_requested_result(self, result):
    """called for each new Result(), regardless of who requested it"""
    pass

class PureRandom(SearchTechnique):
  """
  request configurations completely randomly
  """
  def desired_configuration(self):
    return self.manipulator.random()

class AsyncProceduralSearchTechnique(SearchTechnique):
  def __init__(self, *pargs, **kwargs):
    super(AsyncProceduralSearchTechnique, self).__init__(*pargs, **kwargs)
    self.gen = None
    self.done = False
    self.latest_results = []

  def call_main_generator(self):
    """passthrough (used in subclasses)"""
    return self.main_generator()

  def desired_configuration(self):
    if self.gen is None:
      log.debug("%s: creating generator", self.name)
      self.gen = self.call_main_generator()
    if not self.done:
      try:
        return self.gen.next()
      except StopIteration:
        log.debug("%s: generator finished", self.name)
        self.done = True
    return None

  @abc.abstractmethod
  def main_generator(self):
    """
    custom generator to conduct this search, should:
    yield config
    to request tests and call driver.get_results() to read the results

    in AsyncProceduralSearchTechnique results are ready at an undefined
    time (`yield None` to stall and wait for them)

    in SequentialSearchTechnique results are ready after the yield
    """
    pass

  def is_ready(self):
    return not self.done

class SequentialSearchTechnique(AsyncProceduralSearchTechnique):
  def __init__(self, novelty_threshold = 50, *pargs, **kwargs):
    super(SequentialSearchTechnique, self).__init__(*pargs, **kwargs)
    self.pending_tests = []
    self.novelty_threshold = novelty_threshold
    self.rounds_since_novel_request = 0

  def yield_nonblocking(self, cfg):
    """
    within self.main_generator() act like `yield cfg`, but don't wait for the
    results until the following yield (spawn/sync style)
    """
    if cfg:
      self.pending_tests.append(cfg)

  def call_main_generator(self):
    """insert waits for results after every yielded item"""
    subgen = self.main_generator()
    self.rounds_since_novel_request = 0
    while True:
      self.rounds_since_novel_request += 1
      if (self.rounds_since_novel_request % self.novelty_threshold) == 0:
        log.warning("%s has not requested a new result for %d rounds",
                    self.name, self.rounds_since_novel_request)
        yield None # give other techniques a shot
      try:
        p = subgen.next()
        if p:
          self.pending_tests.append(p)
      except StopIteration:
        return
      finally:
        for p in self.pending_tests:
          if not self.driver.has_results(p):
            self.rounds_since_novel_request = 0
            yield p

      # wait for all pending_tests to have results
      c = 0
      while self.pending_tests:
        log.debug("%s: waiting for %d pending tests",
                  self.name, len(self.pending_tests))
        c += 1
        if (c % 100) == 0:
          log.error("%s: still waiting for %d pending tests (c=%d)",
                     self.name, len(self.pending_tests), c)

        self.pending_tests = filter(lambda x: not self.driver.has_results(x),
                                    self.pending_tests)
        if self.pending_tests:
          self.rounds_since_novel_request = 0
          yield None # wait

#list of all techniques
the_registry = list()


def register(t):
  the_registry.append(t)

register(PureRandom())


def all_techniques(args):
  #import all modules in search to ensure techniques are Registered
  for f in sorted(os.listdir(os.path.dirname(__file__))):
    m = re.match(r'^(.*)[.]py$', f)
    if m:
      import_module('opentuner.search.'+m.group(1))

  return the_registry


def get_enabled(args):
  techniques = all_techniques(args)
  if args.list_techniques:
    for t in techniques:
      print t.name
    sys.exit(0)

  if not args.technique:
    args.technique = ['AUCBanditMetaTechniqueA']

  for unknown in set(args.technique) - set(map(_.name, techniques)):
    log.error("unknown technique %s", unknown)

  return [t for t in techniques if t.name in args.technique]


def get_root(args):
  from metatechniques import RoundRobinMetaSearchTechnique
  enabled=get_enabled(args)
  if len(enabled) == 1:
    return enabled[0]
  return RoundRobinMetaSearchTechnique(get_enabled(args))

