import unittest
import opentuner
import mock
from opentuner.search.composableevolutionarytechniques import ComposableEvolutionaryTechnique
from opentuner.search import manipulator

def faked_random(nums):
  f = fake_random(nums)
  def inner(*args, **kwargs):
    return f.next()
  return inner

def fake_random(nums):
  i = 0
  while True:
    yield nums[i]
    i = (i+1) % len(nums)

class EmptyComposableEvolutionaryTechnique(ComposableEvolutionaryTechnique):
  def __init__(self, *pargs, **kwargs):
    super(EmptyComposableEvolutionaryTechnique, self).__init__(*pargs, **kwargs)

  def minimum_number_of_parents(self):
    return 4

  def get_parents(self, population):
    cfg = self.manipulator.copy(population[0].config)

    return [cfg]

  def update_population(self, config, population):
    # replace the oldest configuration if the new one is better.
    population[0].config = config

    return population

class ComposableSearchTechniqueTests(unittest.TestCase):

  def setUp(self):
    self.operator_map = {}
    ComposableEvolutionaryTechnique.add_to_map(self.operator_map,
                                  manipulator.PermutationParameter,
                                  "op3_cross", xchoice='op3_cross_CX')
    ComposableEvolutionaryTechnique.add_to_map(self.operator_map,
                                  "FloatArray",
                                  "op3_cross", strength=0.4)
    self.technique = EmptyComposableEvolutionaryTechnique(operator_map = self.operator_map)

  def test_add_to_map(self):
    op_map = {}
    op_map[manipulator.PermutationParameter] = {'op_name': 'op3_cross',
                                                'args': (),
                                                'kwargs': {'xchoice': 'op3_cross_CX'}}
    op_map[manipulator.FloatArray] = {'op_name': 'op3_cross',
                                        'args': (),
                                        'kwargs': {'strength': 0.4}}
    self.assertDictEqual(self.operator_map, op_map)

  def test_get_default_oeprator(self):
    default = self.technique.get_default_operator(manipulator.PermutationParameter)
    self.assertDictEqual(default, {'op_name': 'op1_nop', 'args': [], 'kwargs': {}})


  def test_get_operator(self):
    default = self.technique.get_operator(manipulator.IntegerParameter)
    self.assertDictEqual(default, {'op_name': 'op1_nop', 'args': [], 'kwargs': {}})

    default = self.technique.get_operator(manipulator.PermutationParameter)
    self.assertDictEqual(default, {'op_name': 'op3_cross','args': (),'kwargs': {'xchoice': 'op3_cross_CX'}})

  @mock.patch('opentuner.search.manipulator.PermutationParameter.op3_cross')
  def test_apply_operator(self, op3_cross_func):
    param_instance = manipulator.PermutationParameter('temp', [1,2,3,4,5])
    self.technique.apply_operator(param_instance, ['p1', 'p2', 'p3', 'p4'])
    op3_cross_func.assert_called_once_with('p1', 'p2', 'p3', xchoice='op3_cross_CX')

#TODO tests for RandomThreeParentsComposableTechnique
