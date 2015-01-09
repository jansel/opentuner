import unittest
import opentuner
import random
import numpy
from opentuner.search import manipulator

saved_random = random.random
saved_randint = random.randint
saved_randuniform = random.uniform

def restore_random():
    random.random = saved_random

def restore_randint():
    random.randint = saved_randint

def restore_randuniform():
    random.uniform = saved_randuniform

# helper method for overriding manipulator.random
# nums is a list of numbers
def override_random(nums):
    f = fake_random(nums)
    random.random = lambda : f.next()

def override_randuniform(nums):
    f = fake_random(nums)
    random.uniform = lambda x, y: f.next()

def override_randint(nums):
    f = fake_random(nums)
    random.randint = lambda x, y: f.next()

def fake_random(nums):
    i = 0
    while True:
        yield nums[i]
        i = (i+1) % len(nums)

# test overrides for random.random
def test_random_override():
    override_random([0,.125,215])
    assert manipulator.random.random() == 0
    assert manipulator.random.random() == .125
    assert manipulator.random.random() == 215
    assert manipulator.random.random() == 0
    assert manipulator.random.random() == .125
    assert manipulator.random.random() == 215

    restore_random()
    x = (manipulator.random.random() == 0 and
        manipulator.random.random() == .125 and
        manipulator.random.random() == 215)

    assert x == False

def test_randint_override():
    override_randint([0,.125,215])
    assert manipulator.random.randint(0,6) == 0
    assert manipulator.random.randint(2,5) == .125
    assert manipulator.random.randint(2,7) == 215
    assert manipulator.random.randint(1,5) == 0
    assert manipulator.random.randint(2,6) == .125
    assert manipulator.random.randint(12,18) == 215

    restore_randint()
    x = (manipulator.random.randint(1,5) == 0 or
        manipulator.random.randint(1,5) == .125 or
        manipulator.random.randint(0,7) == 215)

    assert x == False
    assert manipulator.random.randint(1,1) == 1

def test_randuniform_override():
    override_randuniform([0,.125,215])
    assert manipulator.random.uniform(0,6) == 0
    assert manipulator.random.uniform(2,5) == .125
    assert manipulator.random.uniform(2,7) == 215
    assert manipulator.random.uniform(1,5) == 0
    assert manipulator.random.uniform(2,6) == .125
    assert manipulator.random.uniform(12,18) == 215

    restore_randuniform()
    x = (manipulator.random.uniform(1,5) == 0 or
        manipulator.random.uniform(1,5) == .125 or
        manipulator.random.uniform(0,7) == 215)

    assert x == False
    assert manipulator.random.uniform(1,1) == 1


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

        self.param1.set_value(self.config1, [0,1,2,3,4,5,6,7,8,9])
        self.param1.set_value(self.config2, [4,3,2,1,0,9,8,7,6,5])
        self.param1.set_value(self.config3, [1,0,4,2,7,9,5,3,6,8])

    def tearDown(self):
        """
        Ensure that random.random(), random.uniform() and random.randint() are restored
        """
        restore_random()
        restore_randint()
        restore_randuniform()

    def test_op2_random_swap_1_6(self):
        # operator shouuld swap the indices at 1 and 6
        override_randint([1,6])
        self.param1.op2_random_swap(self.cfg, self.config1)

        self.assertEqual(self.param1.get_value(self.cfg),[0,6,2,3,4,5,1,7,8,9])
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,5,6,7,8,9])

    def test_op2_random_invert(self):
        """
        should reverse a section of length 3 starting at index given by randint
        """
        override_randint([7,2])
        self.param1.op2_random_invert(self.cfg, self.config1)
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,2,3,4,5,6,9,8,7])

        self.param1.op2_random_invert(self.cfg, self.config1)
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,4,3,2,5,6,7,8,9])

    def test_op3_cross_PMX_str5(self):
        # should perform PMX with a cut at 0 and crossover size 5
        override_randint([0])
        self.param1.op3_cross(self.cfg, self.config1, self.config3,
                                xchoice='op3_cross_PMX', strength=0.5)
        self.assertEqual(self.param1.get_value(self.cfg),[1,0,4,2,7,5,6,3,8,9])


    def test_op3_swarm_CX_no_cross(self):
        # should perform no cross
        override_randuniform([.4])
        override_randint([5])
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.8)
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,5,6,7,8,9])

    def test_op3_swarm_CX_cross_p1(self):
        # should cross the first parent
        override_randuniform([.4])
        override_randint([5])
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.5, c2="unused")
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,9,6,7,8,5])

    def test_op3_swarm_CX_cross_p2(self):
        # should cross the second parent
        override_randuniform([.4])
        override_randint([5])
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.3, c2="unused")
        self.assertEqual(self.param1.get_value(self.config1),[0,1,2,3,4,9,5,7,6,8])


    def test_op3_cross_PX_5(self):
        # Random cut point = 5 (index = 4)
        override_randint([5])
        self.param1.op3_cross_PX(self.cfg, self.config1, self.config3, 2)
        self.assertEqual(self.param1.get_value(self.cfg),[1,0,4,2,3,5,6,7,8,9])

    def test_op3_cross_PMX_0_d4(self):
        # cut = 2, d = 4
        override_randint([2])
        self.param1.op3_cross_PMX(self.cfg, self.config2, self.config3, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[1,3,4,2,7,9,8,0,6,5])

    def test_op3_cross_PMX_0_d5(self):
        # cut = 0, d = 5
        override_randint([0])
        self.param1.op3_cross_PMX(self.cfg, self.config1, self.config3, 5)
        self.assertEqual(self.param1.get_value(self.cfg),[1,0,4,2,7,5,6,3,8,9])

    def test_op3_cross_CX_5(self):
        # initial replacement at index 5
        override_randint([5])
        self.param1.op3_cross_CX(self.cfg, self.config1, self.config2, "unused")
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,2,3,4,9,6,7,8,5])
        self.param1.op3_cross_CX(self.cfg, self.config1, self.config3, "unused")
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,2,3,4,9,5,7,6,8])

    def test_op3_cross_OX1_3_d4(self):
        # cut at 3
        # d = 4
        override_randint([3])
        self.param1.op3_cross_OX1(self.cfg, self.config1, self.config2, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[2,3,4,1,0,9,8,5,6,7])
        self.param1.op3_cross_OX1(self.cfg, self.config1, self.config3, 4)
        self.assertEqual(self.param1.get_value(self.cfg),[0,1,3,2,7,9,5,4,6,8])

    def test_op3_cross_OX3_2_5_d4(self):
        # cuts at 4,2
        # d = 4
        override_randint([4,2])
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

    def tearDown(self):
        """
        Ensure that random.random(), random.uniform() and random.randint() are restored
        """
        restore_random()
        restore_randint()
        restore_randuniform()

    def test_op3_cross_3_str4(self):
        override_randint([3])
        self.param1.op3_cross(self.cfg, self.config1, self.config2, strength=0.4)

        val = self.param1.get_value(self.cfg)
        expected = [1.0,1.1,1.2,2.3,2.4,2.5,2.6,1.7,1.8,1.9]
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])

    def test_op3_swarm_no_cross(self):
        #should perform no cross
        override_randuniform([.4])
        override_randint([3])
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.8)
        val = self.param1.get_value(self.config1)
        expected = [1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9]
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])


    def test_op3_swarm_cross_p1(self):
        #should cross the first parent
        override_randuniform([.4])
        override_randint([3])
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.5, c2="unused")
        val = self.param1.get_value(self.config1)
        expected = [1.0,1.1,1.2,2.3,2.4,2.5,1.6,1.7,1.8,1.9]
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])


    def test_op3_swarm_cross_p2(self):
        #should cross the second parent
        override_randuniform([.4])
        override_randint([3])
        self.param1.op3_swarm(self.config1, self.config2, self.config3,
                                xchoice='op3_cross_CX', c=0.3, c1=0.3, c2="unused")
        val = self.param1.get_value(self.config1)
        expected = [1.0,1.1,1.2,3.3,3.4,3.5,1.6,1.7,1.8,1.9]
        self.assertEqual(len(val),len(expected))
        for i in range(len(val)):
            self.assertAlmostEqual(val[i], expected[i])

    def test_op3_swarm_parallel(self):
        # r1 = 0.2, r2 = 0.4, velocities = [-2,0,0,0,0,0,1,1.5,2,3]
        # max and min are 4, 0
        override_random([0.2, 0.4])
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




