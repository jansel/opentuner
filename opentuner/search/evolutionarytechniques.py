
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

  def desired_configuration(self, manipulator, driver, i):
    '''
    return a (cfg, priority) that we should test,
    through random mutation and crossover
    '''
    parents = self.selection(driver)
    parents = map(copy.deepcopy, parents)

    if len(parents) > 1:
      cfg = self.crossover(parents, manipulator, driver)
    else:
      cfg = parents[0]

    self.mutation(cfg, manipulator, driver)

    return (cfg, 0.0)


  def mutation(self, cfg, manipulator, driver):
    '''
    mutate cfg in place
    '''
    for param in manipulator.parameters(cfg):
      if random.random() < self.mutation_rate:
        self.mutate_param(cfg, param, manipulator, driver)

  def mutate_param(self, cfg, param, manipulator, driver):
    '''
    mutate single parameter of cfg in place
    '''
    param.randomize(cfg)

  def crossover(self, manipulator, driver):
    assert False

  def selection(self, driver):
    '''return a list of parent configurations to use'''
    if random.random() < self.crossover_rate:
      return [self.select(driver), self.select(driver)]
    else:
      return [self.select(driver)]

  @abc.abstractmethod
  def select(self, driver):
    '''return a single random parent configuration'''
    return cfg

class GreedySelectionMixin(object):
  '''
  EvolutionaryTechnique mixin for greedily selecting the best known
  configuration
  '''
  def select(self, driver):
    '''return a single random parent configuration'''
    best_result = driver.results_query(objective_ordered = True).limit(1).one()
    return best_result.configuration.data

class GreedyMutation(GreedySelectionMixin, EvolutionaryTechnique):
  pass

