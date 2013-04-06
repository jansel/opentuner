import abc
import copy
import random
from opentuner.resultsdb.models import *
from technique import SearchTechnique

class EvolutionaryTechnique(SearchTechnique):
  def __init__(self,
               mutation_rate = 0.1,
               crossover_rate = 0.0,
               must_mutate_count = 1):
    self.mutation_rate = mutation_rate
    self.crossover_rate = crossover_rate
    self.must_mutate_count = must_mutate_count
    super(EvolutionaryTechnique, self).__init__()

  def desired_configuration(self):
    '''
    return a (cfg, priority) that we should test,
    through random mutation and crossover
    '''
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
    '''
    mutate cfg in place
    '''
    params = self.manipulator.parameters(cfg)
    random.shuffle(params)
    for param in params[:self.must_mutate_count]:
      self.mutate_param(cfg, param)
    for param in params[self.must_mutate_count:]:
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

