#!/usr/bin/python
"""
Examples usage of a Python API interface to opentuner.

Unlike the other examples, this code lets the user control the main() of
the program and calls into opentuner to get new configurations to test.
"""

import adddeps  # add opentuner to path in dev mode

import opentuner
from opentuner.api import TuningRunManager
from opentuner.measurement.interface import DefaultMeasurementInterface
from opentuner.resultsdb.models import Result
from opentuner.search.manipulator import ConfigurationManipulator
from opentuner.search.manipulator import IntegerParameter
import logging
import argparse

log = logging.getLogger(__name__)


def test_func(cfg):
  x = cfg['x']
  y = (x - 10) * (x - 10)
  log.debug("f({}) -> {}".format(x, y))
  return y


def main():
    parser = argparse.ArgumentParser(parents=opentuner.argparsers())
    args = parser.parse_args()
    manipulator = ConfigurationManipulator()
    manipulator.add_parameter(IntegerParameter('x', -200, 200))
    interface = DefaultMeasurementInterface(args=args,
                                            manipulator=manipulator,
                                            project_name='examples',
                                            program_name='api_test',
                                            program_version='0.1')
    api = TuningRunManager(interface, args)
    for x in xrange(500):
        desired_result = api.get_next_desired_result()
        if desired_result is None:
          # The search space for this example is very small, so sometimes
          # the techniques have trouble finding a config that hasn't already
          # been tested.  Change this to a continue to make it try again.
          break
        cfg = desired_result.configuration.data
        result = Result(time=test_func(cfg))
        api.report_result(desired_result, result)

    best_cfg = api.get_best_configuration()
    api.finish()
    print 'best x found was', best_cfg['x']

if __name__ == '__main__':
  main()

