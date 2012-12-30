#!../../venv/bin/python
import re
import argparse
import logging
import subprocess
import tempfile 
from pprint import pprint

import deps #fix sys.path
from deps import etree
import opentuner
from opentuner.search.manipulator import (ConfigurationManipulator,
                                         IntegerParameter,
                                         FloatParameter)
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager 
from opentuner.tuningrunmain import TuningRunMain

log = logging.getLogger(__name__)

class PetaBricksInterface(MeasurementInterface):
  def __init__(self, args):
    self.program = args.program
    super(PetaBricksInterface, self).__init__()
  
  def run(self, measurement_driver, desired_result, input):
    time, acc = pbrun([args.program,
                       '--time',
                       '--accuracy',
                       '-n=%d' % input.input_class.size],
                      desired_result.configuration.data)
    result = opentuner.resultsdb.models.Result()
    result.time = time
    result.accuracy = acc
    return result


  def program_version(self):
    return self.file_hash(self.program)

def create_config_manipulator(cfgfile):
  '''helper to create the configuration manipulator'''
  cfg=open(cfgfile).read()
  manipulator = ConfigurationManipulator()

  for m in re.finditer(r" *([a-zA-Z0-9_-]+)[ =]+([0-9e.+-]+) *[#] *([a-z]+).* ([0-9]+) to ([0-9]+)", cfg):
    k, v, valtype, minval, maxval =  m.group(1,2,3,4,5)
    assert valtype=='int'
    manipulator.add_cartesian_parameter(IntegerParameter(k, minval, int(maxval)))
  
  return manipulator

def pbrun(cmd_prefix, cfg):
  '''
  helper to run a given petabricks configuration and return (time, accuracy)
  '''

  with tempfile.NamedTemporaryFile(suffix='.petabricks.cfg') as cfgtmp:
    for k,v in cfg.iteritems():
      print >>cfgtmp, k, '=', v
    cfgtmp.flush()
    cmd = cmd_prefix + ['--config', cfgtmp.name]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

  try:
    root = etree.XML(out)
    time = float(root.find('stats/timing').get('average'))
    acc  = float(root.find('stats/accuracy').get('average'))
    return time, acc
  except:
    log.exception("run failed: stderr=%s // stdout=%s", out, err)
    raise

def main(args):
  m = TuningRunMain(
        create_config_manipulator(args.program_cfg_default),
        PetaBricksInterface(args),
        FixedInputManager(size=200),
        args)
  m.main()

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  #logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)
  parser = argparse.ArgumentParser(parents=opentuner.argparsers())
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


