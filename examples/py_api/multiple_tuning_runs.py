#!/usr/bin/python
"""
Examples usage of a Python API interface to opentuner.

Unlike the other examples, this code lets the user control the main() of
the program and calls into opentuner to get new configurations to test.

This version runs multiple tuning runs at once in a single process.
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


def test_func1(cfg):
  x = cfg['x']
  y = (x - 10) * (x - 10)
  log.debug("f({}) -> {}".format(x, y))
  return y


def test_func2(cfg):
  x = cfg['x']
  y = (x + 10) * (x + 10)
  log.debug("f({}) -> {}".format(x, y))
  return y


def test_func3(cfg):
  x = cfg['x']
  y = (x + 20) * (x + 20)
  log.debug("f({}) -> {}".format(x, y))
  return y


def create_test_tuning_run(db):
  parser = argparse.ArgumentParser(parents=opentuner.argparsers())
  args = parser.parse_args()
  args.database = db
  manipulator = ConfigurationManipulator()
  manipulator.add_parameter(IntegerParameter('x', -200, 200))
  interface = DefaultMeasurementInterface(args=args,
                                          manipulator=manipulator,
                                          project_name='examples',
                                          program_name='api_test',
                                          program_version='0.1')
  api = TuningRunManager(interface, args)
  return api


def main():
    apis = [create_test_tuning_run('sqlite:////tmp/a.db'),
            create_test_tuning_run('sqlite:////tmp/b.db'),
            create_test_tuning_run('sqlite:////tmp/c.db')]
    test_funcs = [test_func1, test_func2, test_func3]
    for x in xrange(100):
      for api, test_func in zip(apis, test_funcs):
        desired_result = api.get_next_desired_result()
        if desired_result is None:
          continue
        cfg = desired_result.configuration.data
        result = Result(time=test_func(cfg))
        api.report_result(desired_result, result)

    best_cfgs = [api.get_best_configuration() for api in apis]
    for api in apis:
      api.finish()

    print('best x configs: {}'.format(best_cfgs))

if __name__ == '__main__':
  main()

