#!../../venv/bin/python
import re
import argparse
import logging
import subprocess
import tempfile 
from pprint import pprint

import deps #fix sys.path
import opentuner
from opentuner.search.manipulator import (ConfigurationManipulator,
                                         IntegerParameter,
                                         FloatParameter)
from opentuner.search.driver import SearchDriver
from opentuner.measurement import MeasurementInterface

class PetaBricksMeasurment(MeasurementInterface):
  def __init__(self, args):
    self.cmd_prefix = [
        args.program,
        '--time',
        '--accuracy',
      ]

  def test_configuration(self, measurement_driver, cfg):

    with tempfile.NamedTemporaryFile(suffix='.petabricks.cfg') as cfgtmp:
      for k,v in cfg.iteritems():
        print >>cfgtmp, k, '=', v
      cfgtmp.flush()
      cmd = self.cmd_prefix + [
          '-n', str(10000),
          '--config', cfgtmp.name,
        ]
      p = subprocess.Popen(cmd,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
      out, err = p.communicate()


    print out
    print err



def create_config_manipulator(cfgfile):
  cfg=open(cfgfile).read()
  manipulator = ConfigurationManipulator()

  for m in re.finditer(r" *([a-zA-Z0-9_-]+)[ =]+([0-9e.+-]+) *[#] *([a-z]+).* ([0-9]+) to ([0-9]+)", cfg):
    k, v, valtype, minval, maxval =  m.group(1,2,3,4,5)
    assert valtype=='int'
    manipulator.add_cartesian_parameter(IntegerParameter(k, minval, maxval))
  
  return manipulator


def main(args):
  driver = SearchDriver(create_config_manipulator(args.program_cfg_default), args)
  driver.main()

  tester = PetaBricksMeasurment(args)
  tester.test_configuration(None, driver.manipulator.random())

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)
  parser = argparse.ArgumentParser(parents=[opentuner.search.driver.argparser])
  parser.add_argument('program',
                      help='PetaBricks binary program to autotune')
  parser.add_argument('--program-cfg-default',
                      help="override default program config exemplar file location")
  parser.add_argument('--program-settings',
                      help="override default program settings file location")
  args = parser.parse_args()

  if not args.program_cfg_default:
    args.program_cfg_default = args.program + '.cfg.default'
  
  if not args.program_settings:
    args.program_settings = args.program + '.settings'

  main(args)


