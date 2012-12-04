#!../../venv/bin/python
import re
import argparse
from pprint import pprint

import deps #fix sys.path
from opentuner.search.manipulator import (ConfigurationManipulator,
                                         IntegerParameter,
                                         FloatParameter)
from opentuner.search.driver import SearchDriver
import opentuner


def create_config_manipulator(cfgfile):
  cfg=open(cfgfile).read()
  manipulator = ConfigurationManipulator()

  for m in re.finditer(r" *([a-zA-Z0-9_-]+)[ =]+([0-9e.+-]+) *[#] *([a-z]+).* ([0-9]+) to ([0-9]+)", cfg):
    k, v, valtype, minval, maxval =  m.group(1,2,3,4,5)
    assert valtype=='int'
    manipulator.add_cartesian_parameter(IntegerParameter(k, minval, maxval))
  
  return manipulator

def main(args):
  driver = SearchDriver(create_config_manipulator(args.cfgfile), args)
  driver.main()

if __name__ == '__main__':
  parser = argparse.ArgumentParser(parents=[opentuner.search.driver.argparser])
  args = parser.parse_args()
  args.cfgfile = 'linux_static_x86_64/Sort2.cfg.default'
  main(args)


