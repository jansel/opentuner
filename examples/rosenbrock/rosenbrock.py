#!../../venv/bin/python
#
# This is a simple testcase purely for testing the autotuner
#
# http://en.wikipedia.org/wiki/Rosenbrock_function
#
# Also supports some other test functions taken from:
# http://en.wikipedia.org/wiki/Test_functions_for_optimization
#
import argparse
import logging

import deps #fix sys.path
import opentuner
from opentuner.search.manipulator import (ConfigurationManipulator,
                                          IntegerParameter,
                                          FloatParameter)
from opentuner.search.objective import MinimizeTime
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager
from opentuner.tuningrunmain import TuningRunMain

log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('--dimensions', type=int, default=2,
                    help='dimensions for the Rosenbrock function')
parser.add_argument('--domain', type=float, default=1000,
                    help='bound for variables in each dimension')
parser.add_argument('--function', default='rosenbrock',
                    choices = ('rosenbrock', 'sphere', 'beale'),
                    help='function to use')


class Rosenbrock(MeasurementInterface):
  def __init__(self, args):
    super(Rosenbrock, self).__init__(
        args    = args,
        program = args.function,
        version = "%dx%d" % (args.dimensions, args.domain)
      )

  def run(self, desired_result, input, limit):
    cfg = desired_result.configuration.data
    val = 0.0
    if self.args.function == 'rosenbrock':
      # the actual rosenbrock function:
      for d in xrange(self.args.dimensions-1):
        x0 = cfg['x%d'%d]
        x1 = cfg['x%d'%(d+1)]
        val += 100.0 * (x1 - x0**2)**2 + (x0 - 1)**2
    elif self.args.function == 'sphere':
      for d in xrange(self.args.dimensions):
        xi = cfg['x%d'%d]
        val += xi ** 2
    elif self.args.function == 'beale':
      assert self.args.dimensions == 2
      assert self.args.domain == 4.5
      x = cfg['x0']
      y = cfg['x1']
      val = (
          (1.5   - x + x * y   )**2 +
          (2.25  - x + x * y**2)**2 +
          (2.625 - x + x * y**3)**2
        )
    return opentuner.resultsdb.models.Result(time=val)

def main(args):
  logging.basicConfig(level=logging.INFO)
  if not args.database:
    args.database = 'sqlite:///rosenbrock.db'


  if args.function == 'beale':
    # fixed for this function
    args.domain = 4.5
    args.dimensions = 2

  manipulator = ConfigurationManipulator()
  for d in xrange(args.dimensions):
    manipulator.add_parameter(FloatParameter('x%d'%d ,
                                             -args.domain,
                                             args.domain))
  m = TuningRunMain(manipulator,
                    Rosenbrock(args),
                    FixedInputManager(),
                    MinimizeTime(),
                    args)
  m.main()

if __name__ == '__main__':
  main(parser.parse_args())

