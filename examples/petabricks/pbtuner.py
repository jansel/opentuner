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
                                         LogIntegerParameter,
                                         FloatParameter,
                                         LogFloatParameter,
                                         SwitchParameter,
                                         )
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager
from opentuner.tuningrunmain import TuningRunMain
from opentuner.stats import StatsMain
from opentuner.search.objective import ThresholdAccuracyMinimizeTime

log = logging.getLogger(__name__)

class PetaBricksInterface(MeasurementInterface):
  def program_name(self):    return self.args.program
  def program_version(self): return self.file_hash(self.args.program)

  def run(self, desired_result, input, limit):
    limit = min(limit, self.args.upper_limit)
    with tempfile.NamedTemporaryFile(suffix='.petabricks.cfg') as cfgtmp:
      for k,v in desired_result.configuration.data.iteritems():
        print >>cfgtmp, k, '=', v
      cfgtmp.flush()
      cmd = [args.program,
             '--time',
             '--accuracy',
             '--max-sec=%.8f' % limit,
             '-n=%d' % input.input_class.size,
             '--config', cfgtmp.name]
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      out, err = p.communicate()

    result = opentuner.resultsdb.models.Result()
    try:
      root = etree.XML(out)
      result.time     = float(root.find('stats/timing').get('average'))
      result.accuracy = float(root.find('stats/accuracy').get('average'))
      if result.time < limit + 3600:
        result.status = 'OK'
      else:
        #time will be 2**31 if timeout
        result.status = 'TIMEOUT'
    except:
      result.status   = 'ERROR'
      result.time     = float('inf')
      result.accuracy = float('-inf')
    return result


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
    if minval == 0 and maxval < 64:
      manipulator.add_parameter(SwitchParameter(k, maxval))
    else:
      manipulator.add_parameter(LogIntegerParameter(k, minval, maxval))

  return manipulator

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
  logging.basicConfig(level=logging.INFO)
  #logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)
  parser = argparse.ArgumentParser(parents=opentuner.argparsers())
  parser.add_argument('program',
                      help='PetaBricks binary program to autotune')
  parser.add_argument('--program-cfg-default',
                      help="override default program config exemplar location")
  parser.add_argument('--program-settings',
                      help="override default program settings file location")
  parser.add_argument('--upper-limit', type=float, default=30,
                      help="time limit to apply to initial test")
  args = parser.parse_args()

  if not args.program_cfg_default:
    args.program_cfg_default = args.program + '.cfg.default'

  if not args.program_settings:
    args.program_settings = args.program + '.settings'

  main(args)


