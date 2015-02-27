import abc
import argparse
import logging
import os
import random
import sys

from importlib import import_module
from datetime import datetime
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
argparser.add_argument('--generate-bandit-technique','-gbt', action='store_true',
                       help="randomly generate a bandit to use")

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
    """
    create and return a resultsdb.models.DesiredResult
    returns None if no desired results and False if waiting for results
    """
    cfg = self.desired_configuration()
    if cfg is None:
      return None
    if cfg is False:
      return False
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
    return None if there are no configurations to test
    return False if waiting for results
    """
    return dict()

  def handle_requested_result(self, result):
    """called for each new Result(), regardless of who requested it"""
    pass

  def default_generated_name(self):
    """ The default generated name for this technique """
    return self.base_name()

  def use_default_generated_name(self):
    """ set the name of this technique to the default generated name """
    self.name = self.default_generated_name()

  def base_name(self):
    """
    Return the base name of this technique with form
    classname;hyperparam1,v1;hyperparam2,v2 ...
    where hyperparams are taken in order from get_hyper_parameters()

    Should only be called after this technique has finished initializing.
    """
    out = [self.__class__.__name__]
    for hyper_parameter in self.get_hyper_parameters():
      # get hyperparam,v as a string and append
      try:
        out.append(hyper_parameter + ',' + str(getattr(self, hyper_parameter)))
      except AttributeError:
        log.error("Uninitialized hyper-parameter %s for technique %s.",
                   hyper_parameter, self.__class__.__name__)

    return ';'.join(out)

  @classmethod
  def get_hyper_parameters(cls):
    """
    return a list of hyper-parameters names for this technique

    Name strings must match the corresponding attribute with the hyper-parameter
    value on technique instances. Names should also match the key word argument
    used when initializing an instance. Hyperparameters should only take literal
    values.

    For example, given hyper parameter "mutation_rate", then the __init__ method
    should have 'mutation_rate' as a key word argument and later have the line
    self.mutation_rate = mutation_rate
    """
    return []

  @classmethod
  def generate_technique(cls, manipulator=None, *args, **kwargs):
    """ return a new technique based off this instance """
    t = cls(*args, **kwargs)
    t.use_default_generated_name()
    return t

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
    time (`yield False` to stall and wait for them)

    in SequentialSearchTechnique results are ready after the yield
    """
    pass

  def is_ready(self):
    return not self.done

class SequentialSearchTechnique(AsyncProceduralSearchTechnique):
  def __init__(self, novelty_threshold=50, reset_threshold=500, *pargs, **kwargs):
    super(SequentialSearchTechnique, self).__init__(*pargs, **kwargs)
    self.pending_tests = []
    self.novelty_threshold = novelty_threshold
    self.rounds_since_novel_request = 0
    self.reset_threshold = reset_threshold

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
        if (self.rounds_since_novel_request > self.reset_threshold):
          log.warning("%s is being reset", self.name)
          subgen = self.main_generator()
          self.rounds_since_novel_request = 0
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
          yield False # wait

#list of all techniques
the_registry = list()

#list of technique generators
the_generator_registry = list()

def register(t):
  the_registry.append(t)

def register_generator(cls, generator_weight=1.0, *args, **kwargs):
  """
  register a technique generator - a tuple of (technique class, args, kwargs)
  where args and kwargs will be passed into the generate_technique classmethod -
  with specified probability weight when randomly choosing a generator

  :param cls: a technique class to use as a generator
  :param generator_weight: probability weighting when randomly choosing a generator
  :param args: arguments to pass into generate_technique class method
  :param kwargs: arguments to pass into generate_technique class method
  """
  the_generator_registry.append(((cls, args, kwargs), generator_weight))

register(PureRandom())

def get_random_generator_technique(generators=None, manipulator=None):
  """
  Takes in a sequence of ((generator, args, kwargs), weight) tuples.
  Returns a random generated technique info tuple

  :param generators: optional argument to avoid repeated getting of generators
  :param manipulator: manipulator to pass to generate_technique class method.
  """
  if generators is None:
    techniques, generators = all_techniques()
  g, args, kwargs = weighted_choice(generators)
  return g.generate_technique(manipulator, *args, **kwargs)


def weighted_choice(choices):
  """ takes in a sequence of (choice, weight) tuples and randomly returns one """
  total = sum(w for c, w in choices)
  r = random.uniform(0, total)
  upto = 0
  for c, w in choices:
    upto += w
    if upto > r:
      return c
  return random.choice([c for c, w in choices])


def all_techniques():
  #import all modules in search to ensure techniques are Registered
  for f in sorted(os.listdir(os.path.dirname(__file__))):
    m = re.match(r'^(.*)[.]py$', f)
    if m:
      import_module('opentuner.search.'+m.group(1))

  return the_registry, the_generator_registry

def get_enabled(args):
  techniques, generators = all_techniques()
  if args.list_techniques:
    for t in techniques:
      print t.name
    sys.exit(0)

  if not args.technique:
    # no techniques specified, default technique
    args.technique = ['AUCBanditMetaTechniqueA']

  for unknown in set(args.technique) - set(map(_.name, techniques)):
    log.error('unknown technique %s', unknown)
    raise Exception('Unknown technique: --technique={}'.format(unknown))

  return [t for t in techniques if t.name in args.technique]

def get_root(args):
  from metatechniques import RoundRobinMetaSearchTechnique
  enabled = get_enabled(args)
  if len(enabled) == 1:
    return enabled[0]
  return RoundRobinMetaSearchTechnique(get_enabled(args))

