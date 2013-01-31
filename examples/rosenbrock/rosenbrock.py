#!../../venv/bin/python
#
# This is a simple testcase purely for testing the autotuner
#
# http://en.wikipedia.org/wiki/Rosenbrock_function
#
import argparse
import logging

import deps #fix sys.path
import opentuner
from opentuner.search.manipulator import (ConfigurationManipulator,
                                          IntegerParameter,
                                          FloatParameter)
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager
from opentuner.tuningrunmain import TuningRunMain

log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('--dimensions', type=int, default=2,
                    help='dimensions for the Rosenbrock function')
parser.add_argument('--domain', type=float, default=1000,
                    help='bound for variables in each dimension')

class Rosenbrock(MeasurementInterface):
  def __init__(self, args):
    self.args = args
    super(Rosenbrock, self).__init__()

  def run(self, measurement_driver, desired_result, input):
    cfg = desired_result.configuration.data

    # the actual rosenbrock function:
    val = 0.0
    for d in xrange(self.args.dimensions-1):
      x0 = cfg['x%d'%d]
      x1 = cfg['x%d'%(d+1)]
      val += 100.0 * (x1 - x0**2)**2 + (x0 - 1)**2

    result = opentuner.resultsdb.models.Result()
    result.time = val
    return result

def main(args):
  logging.basicConfig(level=logging.DEBUG)
  if not args.database:
    args.database = 'sqlite:///rosenbrock.db'

  manipulator = ConfigurationManipulator()
  for d in xrange(args.dimensions):
    manipulator.add_parameter(FloatParameter('x%d'%d ,
                                             -args.domain,
                                             args.domain))
  m = TuningRunMain(manipulator,
                    Rosenbrock(args),
                    FixedInputManager(),
                    args)
  m.main()

if __name__ == '__main__':
  main(parser.parse_args())

