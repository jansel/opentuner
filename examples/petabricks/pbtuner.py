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

log = logging.getLogger("pbtuner")

parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('program',
                    help='PetaBricks binary program to autotune')
parser.add_argument('--program-cfg-default',
                    help="override default program config exemplar location")
parser.add_argument('--program-cfg-output',
                    help="location final autotuned configuration is written")
parser.add_argument('--program-settings',
                    help="override default program settings file location")
parser.add_argument('--program-input',
                    help="use only a given input for autotuning")
parser.add_argument('--upper-limit', type=float, default=90,
                    help="time limit to apply to initial test")

class PetaBricksInterface(MeasurementInterface):
  def __init__(self, args):
    self.program_settings = json.load(open(args.program_settings))
    input_manager = FixedInputManager(size=self.program_settings['n'])
    objective = ThresholdAccuracyMinimizeTime(self.program_settings['accuracy'])

    # pass many settings to parent constructor
    super(PetaBricksInterface, self).__init__(
        args,
        program_name = args.program,
        program_version = self.file_hash(args.program),
        input_manager = input_manager,
        objective = objective,
      )

  def run(self, desired_result, input, limit):
    limit = min(limit, self.args.upper_limit)
    with tempfile.NamedTemporaryFile(suffix='.petabricks.cfg') as cfgtmp:
      for k,v in desired_result.configuration.data.iteritems():
        print >>cfgtmp, k, '=', v
      cfgtmp.flush()
      if args.program_input:
        input_opts = ['--iogen-run='+args.program_input,
                      '--iogen-n=%d' % input.input_class.size]
      else:
        input_opts = ['-n=%d' % input.input_class.size]

      cmd = [args.program,
             '--time',
             '--accuracy',
             '--max-sec=%.8f' % limit,
             '--config='+cfgtmp.name] + input_opts
      log.debug("cmd: %s", ' '.join(cmd))
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
      log.warning("program crash, out = %s / err = %s", out, err)
      result.status   = 'ERROR'
      result.time     = float('inf')
      result.accuracy = float('-inf')
    return result

  def save_final_config(self, configuration):
    '''
    called at the end of autotuning with the best resultsdb.models.Configuration
    '''
    with open(args.program_cfg_output, 'w') as fd:
      for k,v in sorted(configuration.data.items()):
        print >>fd, k, '=', v
    log.info("final configuration written to %s", args.program_cfg_output)

  def manipulator(self):
    '''create the configuration manipulator, from example config'''
    upper_limit = self.program_settings['n']+1
    cfg = open(self.args.program_cfg_default).read()
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

if __name__ == '__main__':
  args = parser.parse_args()
  if not args.program_cfg_default:
    args.program_cfg_default = args.program + '.cfg.default'
  if not args.program_cfg_output:
    args.program_cfg_output = args.program + '.cfg'
  if not args.program_settings:
    args.program_settings = args.program + '.settings'
  PetaBricksInterface.main(args)


