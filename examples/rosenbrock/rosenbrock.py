#!/usr/bin/env python
#
# This is a simple testcase purely for testing the autotuner
#
# http://en.wikipedia.org/wiki/Rosenbrock_function
#
# Also supports some other test functions taken from:
# http://en.wikipedia.org/wiki/Test_functions_for_optimization
#

import adddeps  # fix sys.path

import argparse
import logging

import opentuner
from opentuner.measurement import MeasurementInterface
from opentuner.search.manipulator import ConfigurationManipulator
from opentuner.search.manipulator import FloatParameter

log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('--dimensions', type=int, default=2,
                    help='dimensions for the Rosenbrock function')
parser.add_argument('--domain', type=float, default=1000,
                    help='bound for variables in each dimension')
parser.add_argument('--function', default='rosenbrock',
                    choices=('rosenbrock', 'sphere', 'beale'),
                    help='function to use')


class Rosenbrock(MeasurementInterface):
  def run(self, desired_result, input, limit):
    cfg = desired_result.configuration.data
    val = 0.0
    if self.args.function == 'rosenbrock':
      # the actual rosenbrock function:
      for d in xrange(self.args.dimensions - 1):
        x0 = cfg[d]
        x1 = cfg[d + 1]
        val += 100.0 * (x1 - x0 ** 2) ** 2 + (x0 - 1) ** 2
    elif self.args.function == 'sphere':
      for d in xrange(self.args.dimensions):
        xi = cfg[d]
        val += xi ** 2
    elif self.args.function == 'beale':
      assert self.args.dimensions == 2
      assert self.args.domain == 4.5
      x = cfg[0]
      y = cfg[1]
      val = ((1.5 - x + x * y) ** 2 +
             (2.25 - x + x * y ** 2) ** 2 +
             (2.625 - x + x * y ** 3) ** 2)
    return opentuner.resultsdb.models.Result(time=val)

  def manipulator(self):
    manipulator = ConfigurationManipulator()
    for d in xrange(self.args.dimensions):
      manipulator.add_parameter(FloatParameter(d,
                                               -self.args.domain,
                                               self.args.domain))
    return manipulator

  def program_name(self):
    return self.args.function

  def program_version(self):
    return "%dx%d" % (self.args.dimensions, self.args.domain)

  def save_final_config(self, configuration):
    """
    called at the end of autotuning with the best resultsdb.models.Configuration
    """
    print "Final configuration", configuration.data


if __name__ == '__main__':
  args = parser.parse_args()
  if args.function == 'beale':
    # fixed for this function
    args.domain = 4.5
    args.dimensions = 2
  Rosenbrock.main(args)

