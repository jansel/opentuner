#!/usr/bin/env python
#
# This is a quantum control example motivated by the experimental need
# to synthesize unitary matrices in SU(2) in optimal time, given an
# explicit and finite control set generating the whole space, and an
# admissible error.
#
# See problem_description.pdf for additional details.
#
# Contributed by Clarice D. Aiello <clarice@mit.edu>
#

import adddeps  # fix sys.path

import argparse
import logging
import math
import random
import sys

try:
  import numpy as np
except:
  print >> sys.stderr, '''

ERROR: import numpy failed, please install numpy

Possible things to try:
  ../../venv/bin/pip install numpy
  ../../venv/bin/easy_install numpy
  sudo apt-get install python-numpy

'''
  raise

import opentuner

from math import sqrt
import cla_func
from input_generator import (generate_random_Ugoal_HARD,
                             generate_random_Ugoal_EASY,
                             generate_random_Ugoal_RANDOM)

from opentuner.search.manipulator import (ConfigurationManipulator,
                                          SwitchParameter,
                                          IntegerParameter,
                                          FloatParameter)


def generate_random_Ugoal_FIXED(**kwargs):
  Ag = -1 / sqrt(10);
  Bg = sqrt(2) / sqrt(10);
  Cg = -sqrt(3) / sqrt(10);
  Dg = -sqrt(4) / sqrt(10);
  return cla_func.np.matrix(
    [[Ag + Cg * 1j, Bg + Dg * 1j], [-Bg + Dg * 1j, Ag - Cg * 1j]])


log = logging.getLogger(__name__)

generators = {
  'hard': generate_random_Ugoal_HARD,
  'easy': generate_random_Ugoal_EASY,
  'random': generate_random_Ugoal_RANDOM,
  'fixed': generate_random_Ugoal_FIXED,
}

parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('--seq-len', type=int, default=10,
                    help='maximum length for generated sequence')
parser.add_argument('--goal-type', choices=generators.keys(), default='hard',
                    help='method used to generate goal')
parser.add_argument('--goal-n', type=int, default=100,
                    help='argument to ugoal generator')
parser.add_argument('--goal-alpha', type=float,
                    default=random.random() * math.pi,
                    help='argument to ugoal generator')


class Unitary(opentuner.measurement.MeasurementInterface):
  def __init__(self, *pargs, **kwargs):
    super(Unitary, self).__init__(*pargs, **kwargs)

    self.op = cla_func.Op()
    self.num_operators = len(self.op.M)
    self.Ugoal = generators[args.goal_type](N=args.goal_n,
                                            alpha=args.goal_alpha)


  def run(self, desired_result, input, limit):
    cfg = desired_result.configuration.data

    sequence = [cfg[i] for i in xrange(self.args.seq_len)
                if cfg[i] < self.num_operators]
    # sequence can be shorter than self.args.seq_len with null operator

    if len(sequence) > 0:
      accuracy = cla_func.calc_fidelity(sequence, self.op, self.Ugoal)
      # ~.99 is acceptable
    else:
      accuracy = 0.0

    return opentuner.resultsdb.models.Result(time=0.0,
                                             accuracy=accuracy,
                                             size=len(sequence))

  def manipulator(self):
    manipulator = ConfigurationManipulator()
    for d in xrange(self.args.seq_len):
      # we add 1 to num_operators allow a ignored 'null' operator
      manipulator.add_parameter(SwitchParameter(d, self.num_operators + 1))
    return manipulator

  def save_final_config(self, configuration):
    '''
    called at the end of autotuning with the best resultsdb.models.Configuration
    '''
    cfg = configuration.data
    sequence = [cfg[i] for i in xrange(self.args.seq_len)
                if cfg[i] < self.num_operators]
    print "Final sequence", sequence

  def objective(self):
    # we could have also chosen to store 1.0 - accuracy in the time field
    # and use the default MinimizeTime() objective
    return opentuner.search.objective.MaximizeAccuracyMinimizeSize()


if __name__ == '__main__':
  args = parser.parse_args()
  Unitary.main(args)





