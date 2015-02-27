import abc
import copy
import random
from technique import SearchTechnique
from opentuner.search import technique

class GlobalEvolutionaryTechnique(SearchTechnique):
  def __init__(self,
               mutation_rate = 0.1,
               crossover_rate = 0.0,
               must_mutate_count = 1,
	             crossover_strength = 0.1,
               *pargs, **kwargs):
    super(GlobalEvolutionaryTechnique, self).__init__(*pargs, **kwargs)
    self.mutation_rate = mutation_rate
    self.crossover_rate = crossover_rate
    self.must_mutate_count = must_mutate_count
    self.crossover_strength = crossover_strength

  @classmethod
  def get_hyper_parameters(cls):
    return ['mutation_rate', 'crossover_rate', 'must_mutate_count', 'crossover_strength']

  def desired_configuration(self):
    """
    return a (cfg, priority) that we should test,
    through random mutation and crossover
    """
    #TODO: set limit value

    parents = self.selection()
    parents = map(copy.deepcopy, parents)
    parent_hashes = map(self.manipulator.hash_config, parents)

    if len(parents) > 1:
      cfg = self.crossover(parents)
    else:
      cfg = parents[0]

    for z in xrange(10): #retries
      self.mutation(cfg)
      if self.manipulator.hash_config(cfg) in parent_hashes:
        continue # try again
      return cfg

  def mutation(self, cfg):
    """
    mutate cfg in place
    """
    params = self.manipulator.parameters(cfg)
    random.shuffle(params)
    for param in params[:self.must_mutate_count]:
      self.mutate_param(cfg, param)
    for param in params[self.must_mutate_count:]:
      if random.random() < self.mutation_rate:
        self.mutate_param(cfg, param)

  def mutate_param(self, cfg, param):
    """
    mutate single parameter of cfg in place
    """
    param.op1_randomize(cfg)

  def crossover(self, cfgs):
    cfg1, cfg2, = cfgs
    new = self.manipulator.copy(cfg1)
    params = self.manipulator.parameters(cfg1)
    random.shuffle(params)
    d = int(self.crossover_strength*len(params))
    for param in params[:d]:
      param.set_value(new, param.get_value(cfg2))
    return new

  def selection(self):
    """return a list of parent configurations to use"""
    if random.random() < self.crossover_rate:
      return [self.select(),
              self.select()]
    else:
      return [self.select()]

  @abc.abstractmethod
  def select(self):
    """return a single random parent configuration"""
    return None

class GreedySelectionMixin(object):
  """
  EvolutionaryTechnique mixin for greedily selecting the best known
  configuration
  """
  def select(self):
    """return a single random parent configuration"""
    if (self.driver.best_result is not None and
        self.driver.best_result.state == 'OK'):
      return self.driver.best_result.configuration.data
    else:
      return self.manipulator.random()

class NormalMutationMixin(object):
  """
  Mutate primitive parameters according to normal distribution
  """

  def __init__(self, sigma = 0.1, *pargs, **kwargs):
    super(NormalMutationMixin, self).__init__(*pargs, **kwargs)
    self.sigma = sigma

  def mutate_param(self, cfg, param):
    """
    mutate single parameter of cfg in place
    """
    if param.is_primitive():
      param.op1_normal_mutation(cfg, self.sigma)
    else:
      random.choice(param.manipulators(cfg))(cfg)


class UniformGreedyMutation(GreedySelectionMixin, GlobalEvolutionaryTechnique):
  pass

class NormalGreedyMutation(NormalMutationMixin, GreedySelectionMixin, GlobalEvolutionaryTechnique):
  pass

technique.register(NormalGreedyMutation( crossover_rate=0.5, crossover_strength=0.2, name='GGA'))
