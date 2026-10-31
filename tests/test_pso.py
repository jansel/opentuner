import unittest

from opentuner.search import manipulator
from opentuner.search.pso import HybridParticle


class TestHybridParticle(unittest.TestCase):
    def setUp(self):
        self.manipulator = manipulator.ConfigurationManipulator()
        self.manipulator.add_parameter(manipulator.IntegerParameter('x', 0, 1000))
        self.manipulator.add_parameter(manipulator.FloatParameter('y', 0.0, 1000.0))

    def test_move_does_not_change_best(self):
        particle = HybridParticle(self.manipulator, 'op3_cross_OX1')
        best = self.manipulator.copy(particle.best)
        global_best = self.manipulator.random()
        for _ in range(5):
            particle.move(global_best)
        self.assertIsNot(particle.best, particle.position)
        self.assertEqual(particle.best, best)


if __name__ == '__main__':
    unittest.main()
