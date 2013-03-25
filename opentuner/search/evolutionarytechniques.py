import abc
import copy
import random
from opentuner.resultsdb.models import *
from technique import SearchTechnique

class EvolutionaryTechnique(SearchTechnique):
  def __init__(self, mutation_rate = 0.1, crossover_rate = 0.0):
    self.mutation_rate = mutation_rate
    self.crossover_rate = crossover_rate
    super(EvolutionaryTechnique, self).__init__()

  def desired_configuration(self):
    '''
    return a (cfg, priority) that we should test,
    through random mutation and crossover
    '''
    parents = self.selection()
    parents = map(copy.deepcopy, parents)

    if len(parents) > 1:
      cfg = self.crossover(parents)
    else:
      cfg = parents[0]

    self.mutation(cfg)
    return cfg

  def mutation(self, cfg):
    '''
    mutate cfg in place
    '''
    for param in self.manipulator.parameters(cfg):
      if random.random() < self.mutation_rate:
        self.mutate_param(cfg, param)

  def mutate_param(self, cfg, param):
    '''
    mutate single parameter of cfg in place
    '''
    param.randomize(cfg)

  def crossover(self):
    assert False

  def selection(self):
    '''return a list of parent configurations to use'''
    if random.random() < self.crossover_rate:
      return [self.select(),
              self.select()]
    else:
      return [self.select()]

  @abc.abstractmethod
  def select(self):
    '''return a single random parent configuration'''
    return cfg

class GreedySelectionMixin(object):
  '''
  EvolutionaryTechnique mixin for greedily selecting the best known
  configuration
  '''
  def select(self):
    '''return a single random parent configuration'''
    try:
      best_result = (self.driver.results_query(objective_ordered = True)
                                .limit(1)
                                .one())
      return best_result.configuration.data
    except:
      return self.manipulator.random()

class GreedyMutation(GreedySelectionMixin, EvolutionaryTechnique):
  pass

