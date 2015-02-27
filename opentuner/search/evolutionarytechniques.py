import abc
import copy
import random
from technique import SearchTechnique
from opentuner.search import technique

class EvolutionaryTechnique(SearchTechnique):
  def __init__(self,
               mutation_rate = 0.1,
               crossover_rate = 0.0,
               must_mutate_count = 1,
               *pargs, **kwargs):
    super(EvolutionaryTechnique, self).__init__(*pargs, **kwargs)
    self.mutation_rate = mutation_rate
    self.crossover_rate = crossover_rate
    self.must_mutate_count = must_mutate_count

  @classmethod
  def get_hyper_parameters(cls):
    return ['mutation_rate', 'crossover_rate', 'must_mutate_count']


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

  def crossover(self):
    raise Exception('Not implemented')

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


class CrossoverMixin(object):
  def __init__(self, crossover,   *pargs, **kwargs):
    super(CrossoverMixin, self).__init__(*pargs, **kwargs)
    self.crossover_op = crossover
    self.name = 'ga-'+crossover.replace("op3_cross_","")

  def crossover(self, cfgs):
    """
    Crossover the first permtation parameter, if found, of two parents and
    return one offspring cfg
    """
    cfg1, cfg2, = cfgs
    new = self.manipulator.copy(cfg1)
    params = self.manipulator.parameters(cfg1)
    for param in params:
      if param.is_permutation() and param.size>6:
        getattr(param, self.crossover_op)(new, cfg1, cfg2, d=param.size/3)
    return new


class UniformGreedyMutation(GreedySelectionMixin, EvolutionaryTechnique):
  pass

class NormalGreedyMutation(NormalMutationMixin, GreedySelectionMixin, EvolutionaryTechnique):
  pass

class GA(CrossoverMixin, UniformGreedyMutation):
  pass

technique.register(GA(crossover = 'op3_cross_OX3', mutation_rate=0.10, crossover_rate=0.8))
technique.register(GA(crossover = 'op3_cross_OX1', mutation_rate=0.10,crossover_rate=0.8))
technique.register(GA(crossover = 'op3_cross_PX', mutation_rate=0.10, crossover_rate=0.8))
technique.register(GA(crossover = 'op3_cross_CX', mutation_rate=0.10, crossover_rate=0.8))
technique.register(GA(crossover = 'op3_cross_PMX', mutation_rate=0.10, crossover_rate=0.8))
technique.register(UniformGreedyMutation(name='ga-base', mutation_rate=0.10))

technique.register(UniformGreedyMutation(name='UniformGreedyMutation05', mutation_rate=0.05))
technique.register(UniformGreedyMutation(name='UniformGreedyMutation10', mutation_rate=0.10))
technique.register(UniformGreedyMutation(name='UniformGreedyMutation20', mutation_rate=0.20))
technique.register(NormalGreedyMutation(name='NormalGreedyMutation05', mutation_rate=0.05))
technique.register(NormalGreedyMutation(name='NormalGreedyMutation10', mutation_rate=0.10))
technique.register(NormalGreedyMutation(name='NormalGreedyMutation20', mutation_rate=0.20))

