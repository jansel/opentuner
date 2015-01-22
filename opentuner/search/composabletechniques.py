import random
import time
from fn import _
from technique import register
from technique import ComposableSearchTechnique
from manipulator import *

class RandomThreeParentsComposableTechnique(ComposableSearchTechnique):
  """
  based on DifferentialEvolution
  """

  def __init__(self, cr = 0.9, n_cross=1, information_sharing=1, *pargs, **kwargs):
    super(RandomThreeParentsComposableTechnique, self).__init__(*pargs, **kwargs)
    self.cr = cr
    self.n_cross = n_cross
    self.information_sharing = information_sharing

  def minimum_number_of_parents(self):
    return 4

  def get_parents(self, population):
    self.use_f = random.random()
    population.sort(key=_.timestamp) # sort population by timestamp

    # copy oldest
    cfg = self.manipulator.copy(population[0].config)

    shuffled_population = map(_.config, population[1:])
    # mix in the global best configuration
    shuffled_population += ([self.get_global_best_configuration()]
                            * self.information_sharing)
    random.shuffle(shuffled_population)

    # return oldest configuration +_3 other configurations
    return [cfg] + shuffled_population[0:3]

  def update_population(self, config, population):
    # replace the oldest configuration if the new one is better.
    population.sort(key=_.timestamp)
    if self.lt(config, population[0].config):
      population[0].config = config

    # mark that oldest configuration is updated
    population[0].touch

    return population

  def select_parameters(self, params):
    """
    randomly select a subset of parameters to operate on
    """
    ret_list = []
    random.shuffle(params)
    for i, k in enumerate(params):
      if i < self.n_cross or random.random() < self.cr:
        ret_list.append(k)
    return ret_list

  def get_default_operator(self, param_type):
    return {'op_name': 'op4_set_linear', 'args': [1.0, self.use_f, -self.use_f], 'kwargs': {}}


register(RandomThreeParentsComposableTechnique(name='ComposableDiffEvolution',
                                                 population_size=30))

op_map = {}
ComposableSearchTechnique.add_to_map(op_map,
                                      PermutationParameter,
                                      "op3_cross", xchoice='op3_cross_CX')
ComposableSearchTechnique.add_to_map(op_map,
                                      "FloatArray",
                                      "op3_cross", strength=0.4)
register(RandomThreeParentsComposableTechnique(name='ComposableDiffEvolutionCX',
                                                 operator_map=op_map,
                                                 population_size=30))
