import abc
import sys
import os
import logging
import time
from importlib import import_module
from datetime import datetime
import argparse
from fn import _
from opentuner.resultsdb.models import *
from manipulator import *
from opentuner.search.manipulator import Parameter
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
  def __init__(self, novelty_threshold=50, *pargs, **kwargs):
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


class PopulationMember(object):
  """
  An extendable object representing a population member for ComposableSearchTechniques.
  Must have the field "config" which is a configuration
  """
  def __init__(self, config):
    self.config = config
    self.timestamp = time.time()

  def touch(self):
    """
    Update the timestamp on a PopulationMember
    """
    self.timestamp = time.time()


#TODO make docstrings better
class ComposableSearchTechnique(SequentialSearchTechnique):
  """
  An abstract base class for a technique that is composable with operators
  """
  __metaclass__ = abc.ABCMeta

  # operator_map - from param-type to dict with operator name + list of arguments TODO
  # min_parent - minimum number of parents returned. Limits which operators can be used
  # TODO make better name. Should this be an overriden method?
  def __init__(self,
               operator_map = {},
               population_size = 50,
               initial_configs = None,
               *pargs,
               **kwargs):
    super(ComposableSearchTechnique, self).__init__(*pargs, **kwargs)
    self.initial_configurations = initial_configs
    self.population_size = population_size
    self.operator_map = operator_map # map from parameter type to an operator function

  def make_population_member(self, config):
    """
    Given a configuration, returns an object representing a single member of the
    population with the given configuration. Meta-data about the configuration,
    such as last selection time as a parent, can be attached to the object.

    This can be overriden to return a custom population member for use in
    :py:meth:`get_parents` and :py:meth:`update_population`

    :param config: the configuration that this population member will represent
    :return: a population member reresenting the input configuration.
    """
    return PopulationMember(config)

  def select_parameters(self, params):
    """
    Given all the available parameters, return a subset of parameters to operate
    on when generating a new configuration.

    Can override this to operate on only a subset of parameters.

    :param params: a list of all the available parameters
    :return: a subset of params
    """
    return params

  @abc.abstractmethod
  def minimum_number_of_parents(self):
    """
    Return the minimum number of parents ever returned by :py:meth:`get_parents`.
    This limits which operators can be composed with the technique. Operators
    requiring more input configurations than the minimum number of parents will
    result in an error.

    :return: the minimum number of parents ever generated.
    """
    return 1

  @abc.abstractmethod
  def get_parents(self, population):
    """
    Given the current population, return a list of configurations that will be
    used to generate a new configuration via operators. Returning less parents
    than guaranteed by :py:meth:`minimum_number_of_parents` results in an error.

    The parents will be passed to operators in order. If there are more parents
    than required by an operator, extra parents will be discarded.

    Note that operators mutate the first configuration passed in.

    :param population: the current population in the technique
    :return: a list of parent configurations to generate a new configuration from
    """
    pass

  @abc.abstractmethod
  def update_population(self, config, population):
    """
    Update the population given the newest configuration and current population
    in the technique. should return the new population

    :param config: the newest generated configuration
    :param population: the current population in this iteration of the technique
    :return: the updated population
    """
    pass

  def get_initial_population(self):
    """
    Returns an initial population by passing initial configurations into
    :py:meth:`make_population_member`

    :return: an initial list of objects returned by :py:meth:`make_population_member`.
    """
    init_configs = self.initial_configurations
    if not init_configs:
      init_configs = [self.manipulator.random() for i in range(self.population_size)]
    return [PopulationMember(config) for config in init_configs]

  def lt(self, cfg_a, cfg_b):
    """
    Return whether cfg_a has a better objective function score than cfg_b

    :param cfg_a: first configuration
    :param cfg_b: second configuration
    :return: True if cfg_a is better than cfg_b
    """
    def config(cfg):
      return self.driver.get_configuration(cfg)
    return self.objective.lt(config(cfg_a), config(cfg_b))

  def lte(self, cfg_a, cfg_b):
    """
    Return whether cfg_a's objective function score is at least as good as cfg_b's
    score

    :param cfg_a: first configuration
    :param cfg_b: second configuration
    :return: True if cfg_a is at least as good as cfg_b
    """
    def config(cfg):
      return self.driver.get_configuration(cfg)
    return self.objective.lte(config(cfg_a), config(cfg_b))

  def get_global_best_configuration(self):
    """
    Return the current global best configuration in the search

    :return: the current global best configuration
    """
    return self.driver.best_result.configuration.data

  def get_default_operator(self, param_type):
    """
    Given a parameter type, return a dictionary with information about the
    operator to be used for the parameter. The returned dictionary must contain
    the following 3 key, value pairs
      1. 'op_name' - the string name of the operator
      2. 'args' - an iterable of the non-configuration arguments in order
      3. 'kwargs' - a dictionary from any optional arguments to their values

    :return: a dictionary containing information about the operator to apply for
    the input parameter type
    """
    return {'op_name': 'op1_void', 'args': [], 'kwargs': {}}

  # HELPER METHODS FOR BUILDING OPERATOR MAP
  @classmethod
  def add_to_map(cls, operator_map, param_type, operator_name, *args, **kwargs):
    """
    A helper method for adding parameter to operator mappings into the operator
    map.

    :param operator_map: the operator map to add to
    :param param_type: the parameter type to use the this operator on
    :param operator_name: the string name of the operator method
    :param *args: any non-configuration arguments to the operator
    :param **kwargs: any keyword arguemnts for the operator
    """
    if(isinstance(param_type, Parameter)):
      ptype = type(param_type)
    elif (type(param_type) == str):
      ptype = reduce(getattr, param_type.split("."), sys.modules[__name__])
    else:
      ptype = param_type;

    operator_map[ptype] = {'op_name': operator_name, 'args':args, 'kwargs':kwargs}


  def main_generator(self):
    """
    The primary body of the search technique.
    Initializes an initial population and then yields configurations by applying
    operators to get_parents.
    """
    min_parents = self.minimum_number_of_parents();
    # convert a manipulator configuration to a db.models.Configuration
    def get_driver_configuration(cfg):
      return self.driver.get_configuration(cfg)

    # initialize the population
    population = self.get_initial_population()

    # measure initial population
    for p in population:
      yield get_driver_configuration(p.config)

    while True:
      # get parents
      parents = self.get_parents(population)
      if len(parents) < min_parents:
         log.error("%s: Number of parents returned %d is less than the guaranteed"
                     + " minimum returned by minimum_number_of_parents() %d. ",
                     self.name, len(parents), min_parents)
         # fail and let other techniques work forever
         while True:
          yield None


      params = self.select_parameters(self.manipulator.params)
      config = self.get_new_config(parents, params)
      yield get_driver_configuration(config)

      population = self.update_population(config, population)

      # safety check that population has all been tested
      for p in population:
        if not self.driver.has_results(get_driver_configuration(p.config)):
          yield get_driver_configuration(p.config)

  def get_new_config(self, parents, params):
    """
    Return a new configuration to test, given a list of parent configurations
    This mutates the first parent

    :param parents: A list of parent configurations
    :params: A list of parameters to operate on
    :return: The mutated configuration (first parent)
    """
    for param in params:
      self.apply_operator(param, parents) #TODO
    return parents[0]

  def apply_operator(self, param, parents):
    """
    Apply the appropriate operator for param to parents.
    If an operator takes less input configurations than the number of parents,
    only the first parents are passed in. If operator takes more input configs
    than minimum_number_of_parents, logs an error and doesn't do anything
    """
    x = self.get_operator(type(param))

    operator_name = x['op_name']
    if not self.is_valid_operator(type(param), operator_name):
      # do nothing
      return

    # operator is already in valid form and starts with op1, op2, op3, op4, or opn
    num_parents_required = operator_name[2]
    if num_parents_required == 'n':
      args = parents[0] + [parents[1:]]
    else:
      num_parents_required = int(num_parents_required)
      args = parents[:num_parents_required]
    args.extend(x['args'])

    kwargs = x['kwargs']

    getattr(param, operator_name)(*args, **kwargs)

  def get_operator(self, param_type):
    if param_type in self.operator_map:
      return self.operator_map[param_type]
    return self.get_default_operator(param_type)

  def is_valid_operator(self, param_type, operator_name):
    if not hasattr(param_type, operator_name):
      log.error("%s: %s is not a valid operator for Parameter type %s",
                self.name, operator_name, param_type.__name__)
      return False

    if operator_name[:3] not in ['op1','op2','op3','op4','opn']:
      log.error("%s: %s is not a valid operator for Parameter type %s",
                self.name, operator_name, param_type.__name__)
      return False

    num_parents_required = operator_name[2]
    if num_parents_required == 'n':
      return True

    num_parents_required = int(num_parents_required)
    minimum_number_of_parents = self.minimum_number_of_parents()

    if num_parents_required > minimum_number_of_parents:
      log.error("%s: %s for Parameter type %s requires more input configs "
                + "than minimum number of parents, %d, produced by this technique",
                self.name, operator_name, param_type.__name__, minimum_number_of_parents)
      return False

    return True


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
    log.error('unknown technique %s', unknown)
    raise Exception('Unknown technique: --technique={}'.format(unknown))

  return [t for t in techniques if t.name in args.technique]


def get_root(args):
  from metatechniques import RoundRobinMetaSearchTechnique
  enabled = get_enabled(args)
  if len(enabled) == 1:
    return enabled[0]
  return RoundRobinMetaSearchTechnique(get_enabled(args))

