#!../../venv/bin/python
import re
import argparse
import logging
import subprocess
import tempfile
import json
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
from opentuner.stats import StatsMain
from opentuner.search.objective import ThresholdAccuracyMinimizeTime

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

def create_config_manipulator(cfgfile, upper_limit):
  '''helper to create the configuration manipulator'''
  cfg=open(cfgfile).read()
  manipulator = ConfigurationManipulator()

  for m in re.finditer(r" *([a-zA-Z0-9_-]+)[ =]+([0-9e.+-]+) *"
                       r"[#] *([a-z]+).* ([0-9]+) to ([0-9]+)", cfg):
    k, v, valtype, minval, maxval =  m.group(1,2,3,4,5)
    minval = float(minval)
    maxval = float(maxval)
    if upper_limit:
      maxval = min(maxval, upper_limit)
    assert valtype=='int'
    #log.debug("param %s %f %f", k, minval, maxval)
    manipulator.add_parameter(IntegerParameter(k, minval, maxval))

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
  program_settings = json.load(open(args.program_settings))
  log.debug("program_settings: %s", str(program_settings))
  m = TuningRunMain(
        create_config_manipulator(args.program_cfg_default,
                                  program_settings['n']+1),
        PetaBricksInterface(args),
        FixedInputManager(size=program_settings['n']),
        ThresholdAccuracyMinimizeTime(program_settings['accuracy']),
        args)
  m.main()

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  #logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)
  parser = argparse.ArgumentParser(parents=opentuner.argparsers())
  parser.add_argument('program',
                      help='PetaBricks binary program to autotune')
  parser.add_argument('--program-cfg-default',
                      help="override default program config exemplar location")
  parser.add_argument('--program-settings',
                      help="override default program settings file location")
  args = parser.parse_args()

  if not args.database:
    args.database = 'sqlite:///' + args.program + '.db'

  if not args.program_cfg_default:
    args.program_cfg_default = args.program + '.cfg.default'

  if not args.program_settings:
    args.program_settings = args.program + '.settings'

  main(args)


