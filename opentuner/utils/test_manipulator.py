#!/usr/bin/python

if __name__ == '__main__':
  import adddeps

import argparse
import logging
import opentuner
import os
import sys

from collections import defaultdict
from opentuner.search import manipulator
from pprint import pprint

log = logging.getLogger(__name__)

def main(args):
  m = manipulator.ConfigurationManipulator()
  m.add_parameter(manipulator.IntegerParameter(
    'IntegerParameter(10, 15)', 10, 14))
  # m.add_parameter(manipulator.FloatParameter('FloatParameter', 10, 15))
  # m.add_parameter(manipulator.LogFloatParameter('LogFloatParameter', 10, 15))
  m.add_parameter(manipulator.LogIntegerParameter(
    'LogIntegerParameter(10, 15)', 10, 15))
  m.add_parameter(manipulator.PowerOfTwoParameter(
    'PowerOfTwoParameter(2, 16)', 2, 16))
  m.add_parameter(manipulator.BooleanParameter('BooleanParameter()'))
  m.add_parameter(manipulator.SwitchParameter('SwitchParameter(4)', 4))
  m.add_parameter(manipulator.EnumParameter(
    "EnumParameter(['a', 'b', 'c'])", ['a', 'b', 'c']))
  m.add_parameter(manipulator.PermutationParameter(
    "PermutationParameter(['a', 'b', 'c'])", ['a', 'b', 'c']))
  m.add_parameter(manipulator.ScheduleParameter(
    'ScheduleParameter(...)',
    ['a', 'b', 'c', 'd'], {'a': ['b'], 'c': ['d']}))
  m.add_parameter(manipulator.ScheduleParameter(
    'ScheduleParameter(...)',
    ['a', 'b', 'c', 'd'], {'a': ['b'], 'c': ['d']}))
  cfg = m.random()

  print 'Testing distribution produced by param.randomize()...'
  histo = defaultdict(lambda: defaultdict(int))
  for z in xrange(args.n):
    for k, v in cfg.items():
      if type(v) is list:
        v = tuple(v)
      histo[k][v] += 1
    for param in m.parameters(cfg):
      param.randomize(cfg)
  pprint({name: sorted((v / float(args.n), k) for k, v in values.items())
          for name, values in histo.items()})
  print

  print 'Testing distribution produced param.set_unit_value()...'
  histo = defaultdict(lambda: defaultdict(int))
  for z in xrange(args.n):
    for param in m.parameters(cfg):
      if param.is_primitive():
        param.set_unit_value(cfg, z / float(args.n - 1))
        histo[param.name][cfg[param.name]] += 1
  pprint({name: sorted((v / float(args.n), k) for k, v in values.items())
          for name, values in histo.items()})
  print
  print 'BooleanArray'
  m = manipulator.ConfigurationManipulator()
  m.add_parameter(manipulator.BooleanArrayParameter('bools', 10))
  print m.random()


if __name__ == '__main__':
  argparser = argparse.ArgumentParser()
  argparser.add_argument('-n', type=int, default=10000)
  opentuner.tuningrunmain.init_logging()
  sys.exit(main(argparser.parse_args()))
