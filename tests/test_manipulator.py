import unittest
import opentuner
import mock
import random
import numpy
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


class PermutationOperatorTests(unittest.TestCase):

    def setUp(self):
        """
        Set up a few configurations. The values of the PermutationParameter are:
        config1 - 0 1 2 3 4 5 6 7 8 9
        config2 - 4 3 2 1 0 9 8 7 6 5
        config3 - 1 0 4 2 7 9 5 3 6 8

        """
        self.manipulator = manipulator.ConfigurationManipulator()
        self.param1 = manipulator.PermutationParameter("param1", [0,1,2,3,4,5,6,7,8,9])
        self.manipulator.add_parameter(self.param1)

        self.cfg = self.manipulator.seed_config()
        self.config1 = self.manipulator.seed_config()
        self.config2 = self.manipulator.seed_config()
        self.config3 = self.manipulator.seed_config()

        # repeating values
        self.config4 = self.manipulator.seed_config()
        self.config5 = self.manipulator.seed_config()


        self.param1.set_value(self.config1, [0,1,2,3,4,5,6,7,8,9])
        self.param1.set_value(self.config2, [4,3,2,1,0,9,8,7,6,5])
        self.param1.set_value(self.config3, [1,0,4,2,7,9,5,3,6,8])

        # repeating values
        self.param1.set_value(self.config4, [1,2,3,4,2,3,4,3,4,4])
        self.param1.set_value(self.config5, [4,2,4,3,3,1,3,4,2,4])

    @mock.patch('random.randint', side_effect=faked_random([1,6]))
    def test_op2_random_swap_1_6(self, randint_func):
        # operator shouuld swap the indices at 1 and 6
        self.param1.op2_random_swap(self.cfg, self.config1)

        self.assertEqual(self.param1.get_value(self.cfg),[0,6,2,3,4,5,1,7,8,9])
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,5,6,7,8,9])


    @mock.patch('random.randint', side_effect=faked_random([7,2]))
    def test_op2_random_invert(self, randint_func):
        #should reverse a section of length 3 starting at index given by randint
        self.param1.op2_random_invert(self.cfg, self.config1)
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,2,3,4,5,6,9,8,7])

        self.param1.op2_random_invert(self.cfg, self.config1)
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,4,3,2,5,6,7,8,9])


    @mock.patch('random.randint', side_effect=faked_random([0]))
    def test_op3_cross_PMX_str5(self, randint_func):
        # should perform PMX with a cut at 0 and crossover size 5
        self.param1.op3_cross(self.cfg, self.config1, self.config3,
                                xchoice='op3_cross_PMX', strength=0.5)
        self.assertEqual(self.param1.get_value(self.cfg),[1,0,4,2,7,5,6,3,8,9])

    @mock.patch('random.randint', side_effect=faked_random([5]))
    @mock.patch('random.uniform', side_effect=faked_random([0.4]))
    def test_op3_swarm_CX_no_cross(self, uniform_func, randint_func):
        # should perform no cross
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.8)
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,5,6,7,8,9])


    @mock.patch('random.randint', side_effect=faked_random([5]))
    @mock.patch('random.uniform', side_effect=faked_random([0.4]))
    def test_op3_swarm_CX_cross_p1(self, uniform_func, randint_func):
        # should cross the first parent
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.5, c2="unused")
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,9,6,7,8,5])

    @mock.patch('random.randint', side_effect=faked_random([5]))
    @mock.patch('random.uniform', side_effect=faked_random([0.4]))
    def test_op3_swarm_CX_cross_p2(self, uniform_func, randint_func):
        # should cross the second parent
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.3, c2="unused")
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,9,5,7,6,8])


    @mock.patch('random.randint', side_effect=faked_random([5]))
    def test_op3_cross_PX_5(self, randint_func):
        # Random cut point = 5 (index = 4)
        self.param1.op3_cross_PX(self.cfg, self.config1, self.config3, 2)
        self.assertEqual(self.param1.get_value(self.cfg),[1,0,4,2,3,5,6,7,8,9])

    @mock.patch('random.randint', side_effect=faked_random([2]))
    def test_op3_cross_PMX_0_d4(self, randint_func):
        # cut = 2, d = 4
        self.param1.op3_cross_PMX(self.cfg, self.config2, self.config3, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[1,3,4,2,7,9,8,0,6,5])


    @mock.patch('random.randint', side_effect=faked_random([0]))
    def test_op3_cross_PMX_0_d5(self, randint_func):
        # cut = 0, d = 5
        self.param1.op3_cross_PMX(self.cfg, self.config1, self.config3, 5)
        self.assertEqual(self.param1.get_value(self.cfg),[1,0,4,2,7,5,6,3,8,9])

    @mock.patch('random.randint', side_effect=faked_random([4]))
    def test_op3_cross_PMX_dups(self, randint_func):
        # cut = 4, d = 5
        self.param1.op3_cross_PMX(self.cfg, self.config5, self.config4, 5)

        # [4,2,4,3,3,1,3,4,2,4]
        # [1,2,3,4,2,3,4,3,4,4]
        # expected:
        # [1,2,4,3,2,3,4,3,4,4]

        self.assertEqual(self.param1.get_value(self.cfg), [1,2,4,3,2,3,4,3,4,4])


    @mock.patch('random.randint', side_effect=faked_random([5]))
    def test_op3_cross_CX_5(self, randint_func):
        # initial replacement at index 5
        self.param1.op3_cross_CX(self.cfg, self.config1, self.config2, "unused")
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,2,3,4,9,6,7,8,5])
        self.param1.op3_cross_CX(self.cfg, self.config1, self.config3, "unused")
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,2,3,4,9,5,7,6,8])

    @mock.patch('random.randint', side_effect=faked_random([0]))
    def test_op3_cross_CX_dups(self, randint_func):
        # initial replacement at index 4
        self.param1.op3_cross_CX(self.cfg, self.config5, self.config4, "unused")

        # [4,2,4,3,3,1,3,4,2,4]
        # [1,2,3,4,2,3,4,3,4,4]
        # expected:
        # [1,2,3,4,3,3,4,4,2,4]

        self.assertEqual(self.param1.get_value(self.cfg), [1,2,3,4,3,3,4,4,2,4])


    @mock.patch('random.randint', side_effect=faked_random([3]))
    def test_op3_cross_OX1_3_d4(self, randint_func):
        # cut at 3
        # d = 4
        self.param1.op3_cross_OX1(self.cfg, self.config1, self.config2, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[2,3,4,1,0,9,8,5,6,7])
        self.param1.op3_cross_OX1(self.cfg, self.config1, self.config3, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,3,2,7,9,5,4,6,8])

    @mock.patch('random.randint', side_effect=faked_random([4,2]))
    def test_op3_cross_OX3_2_5_d4(self, randint_func):
        # cuts at 4,2
        # d = 4
        self.param1.op3_cross_OX3(self.cfg, self.config1, self.config2, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[3,4,5,6,2,1,0,9,7,8])
        self.param1.op3_cross_OX3(self.cfg, self.config1, self.config3, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,3,5,4,2,7,9,6,8])


class FloatArrayOperatorTests(unittest.TestCase):
    """
    also tests the operators for Array (since Array is abstract)
    """

    def setUp(self):
        """
        Set up a few configurations. The values of the FloatArray are:
        config1 - 1.0 1.1 1.2 1.3 1.4 1.5 1.6 1.7 1.8 1.9
        config2 - 2.0 2.1 2.2 2.3 2.4 2.5 2.6 2.7 2.8 2.9
        config3 - 3.0 3.1 3.2 3.3 3.4 3.5 3.6 3.7 3.8 3.9
        """
        self.manipulator = manipulator.ConfigurationManipulator()
        self.param1 = manipulator.FloatArray("param1", 10, 4, 0)
        self.manipulator.add_parameter(self.param1)

        self.cfg = self.manipulator.seed_config()
        self.config1 = self.manipulator.seed_config()
        self.config2 = self.manipulator.seed_config()
        self.config3 = self.manipulator.seed_config()

        self.param1.set_value(self.config1, numpy.array([1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9]))
        self.param1.set_value(self.config2, numpy.array([2.0,2.1,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9]))
        self.param1.set_value(self.config3, numpy.array([3.0,3.1,3.2,3.3,3.4,3.5,3.6,3.7,3.8,3.8]))


    @mock.patch('random.randint', side_effect=faked_random([3]))
    def test_op3_cross_3_str4(self, randint_func):
        self.param1.op3_cross(self.cfg, self.config1, self.config2, strength=0.4)

        val = self.param1.get_value(self.cfg)
        expected = [1.0,1.1,1.2,2.3,2.4,2.5,2.6,1.7,1.8,1.9]
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])

    @mock.patch('random.randint', side_effect=faked_random([3]))
    @mock.patch('random.uniform', side_effect=faked_random([0.4]))
    def test_op3_swarm_no_cross(self, uniform_func, randint_func):
        #should perform no cross
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.8)
        val = self.param1.get_value(self.config1)
        expected = [1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9]
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])


    @mock.patch('random.randint', side_effect=faked_random([3]))
    @mock.patch('random.uniform', side_effect=faked_random([0.4]))
    def test_op3_swarm_cross_p1(self, uniform_func, randint_func):
        #should cross the first parent
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.5, c2="unused")
        val = self.param1.get_value(self.config1)
        expected = [1.0,1.1,1.2,2.3,2.4,2.5,1.6,1.7,1.8,1.9]
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])


    @mock.patch('random.randint', side_effect=faked_random([3]))
    @mock.patch('random.uniform', side_effect=faked_random([0.4]))
    def test_op3_swarm_cross_p2(self, uniform_func, randint_func):
        #should cross the second parent
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.3, c2="unused")
        val = self.param1.get_value(self.config1)
        expected = [1.0,1.1,1.2,3.3,3.4,3.5,1.6,1.7,1.8,1.9]
        self.assertEqual(len(val),len(expected))
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])

    @mock.patch('random.random', side_effect=faked_random([0.2, 0.4]))
    def test_op3_swarm_parallel(self, random_func):
        # r1 = 0.2, r2 = 0.4, velocities = [-2,0,0,0,0,0,1,1.5,2,3]
        # max and min are 4, 0
        velocities = numpy.array([-2.0,0.0,0,0,0,0,1.0,1.5,2,3.0])

        vs = self.param1.op3_swarm_parallel(self.config1, self.config2, self.config3, velocities=velocities)
        vs_expected = [-1.5,.5,.5,.5,.5,.5,1.5,2.0,2.5,3.48]

        self.assertEqual(len(vs),len(vs_expected))

        for i in range(len(vs)):
            self.assertAlmostEqual(vs[i], vs_expected[i])


        val = self.param1.get_value(self.config1)
        expected = [0,1.6,1.7,1.8,1.9,2.0,3.1,3.7,4,4]
        self.assertEqual(len(val),len(expected))
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])



