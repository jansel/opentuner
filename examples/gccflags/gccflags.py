#!/usr/bin/env python
import adddeps  # fix sys.path

import argparse
import ast
import hashlib
import collections
import itertools
import json
import logging
import math
import opentuner
import os
import random
import re
import subprocess
import sys
import tempfile
import shutil

from opentuner.resultsdb.models import Result, TuningRun
from opentuner.search import manipulator

log = logging.getLogger('gccflags')

argparser = argparse.ArgumentParser(parents=opentuner.argparsers())
argparser.add_argument('source', help='source file to compile')
argparser.add_argument(
  '--compile-template', default='g++ {source} -o {output} {flags}',
  help='command to compile {source} into {output} with {flags}')
argparser.add_argument('--compile-limit', type=float, default=60,
                       help='kill gcc if it runs more than {default} sec')
argparser.add_argument('--scaler', type=int, default=4,
                       help='by what factor to try increasing parameters')
argparser.add_argument('--cc', default='gcc', help='g++ or gcc')
argparser.add_argument('--output', default='./tmp.bin',
                       help='temporary file for compiler to write to')
argparser.add_argument('--debug', action='store_true',
                       help='on gcc errors try to find minimal set '
                            'of args to reproduce error')
argparser.add_argument('--memory-limit', default=1024**3, type=int,
                       help='memory limit for child process')
argparser.add_argument('--flags-histogram', action='store_true',
                       help='print out a histogram of flags')

class GccFlagsTuner(opentuner.measurement.MeasurementInterface):
  def __init__(self, *pargs, **kwargs):
    super(GccFlagsTuner, self).__init__(program_name = args.source, *pargs,
                                        **kwargs)
    self.extract_gcc_options()
    self.result_list = {}
    self.parallel_compile = True
    try:
      os.stat('./tmp')
    except:
      os.mkdir('./tmp')
    # TODO: Set up compile and run option
    # self.run_baselines()

  def run_baselines(self):
    log.info("baseline perfs -O0=%.4f -O1=%.4f -O2=%.4f -O3=%.4f",
              *[self.run_with_flags(['-O%d' % i], None).time 
                for i in range(4)])

  def extract_gcc_options(self):
    """
    called once from __init__ to determine which options are supported by the
    local g++
    """
    if os.path.isfile('cc_flags.json'):
      # use cached version
      self.cc_flags = json.load(open('cc_flags.json'))
    else:
      # extract flags from --help=optimizers
      optimizers, err = subprocess.Popen([self.args.cc, '--help=optimizers'],
                                         stdout=subprocess.PIPE).communicate()
      self.cc_flags = re.findall(r'^  (-f[a-z0-9-]+) ', optimizers,
                                 re.MULTILINE)
      self.cc_flags = filter(self.check_if_flag_works, self.cc_flags)
      json.dump(self.cc_flags, open('cc_flags.json', 'w'))

    if os.path.isfile('cc_param_defaults.json'):
      # use cached version
      self.cc_param_defaults = json.load(open('cc_param_defaults.json'))
    else:
      # default values of params need to be extracted from source code,
      # since they are not in --help
      self.cc_param_defaults = dict()
      params_def = open(os.path.expanduser('~/gcc-4.7.3/gcc/params.def')).read()
      for m in re.finditer(r'DEFPARAM *\((([^")]|"[^"]*")*)\)', params_def):
        try:
          name, desc, default, min, max = ast.literal_eval(
              '[' + m.group(1).split(',', 1)[1] + ']')
          self.cc_param_defaults[name] = {'default': default,
                                          'min': min,
                                          'max': max}
        except:
          log.exception("error with %s", m.group(1))
      json.dump(self.cc_param_defaults, open('cc_param_defaults.json', 'w'))

    # extract params from help=params
    params, err = subprocess.Popen(
      [self.args.cc, '--help=params'], stdout=subprocess.PIPE).communicate()
    self.cc_params = re.findall(r'^  ([a-z0-9-]+) ', params, re.MULTILINE)
    self.cc_params = sorted(set(self.cc_params) &
                            set(self.cc_param_defaults.keys()))

    # these bugs are hardcoded for now
    # sets of options which causes gcc to barf
    self.cc_bugs = (['-fipa-matrix-reorg', '-fwhole-program'],
                    ['-fno-tree-coalesce-inlined-vars'],
                    ['-fno-inline-atomics'],
                    ['-ftoplevel-reorder', '-fno-unit-at-a-time'])


  def check_if_flag_works(self, flag):
    cmd = args.compile_template.format(source=args.source, output=args.output,
                                       flags=flag)
    compile_result = self.call_program(cmd, limit=args.compile_limit)
    if compile_result['returncode'] != 0:
      log.warning("removing flag %s because it results in compile error", flag)
      return False
    if 'warning: this target' in compile_result['stderr']:
      log.warning("removing flag %s because not supported by target", flag)
      return False
    if 'has been renamed' in compile_result['stderr']:
      log.warning("removing flag %s because renamed", flag)
      return False
    return True

  def manipulator(self):
    m = manipulator.ConfigurationManipulator()
    m.add_parameter(manipulator.IntegerParameter('-O', 0, 3))
    for flag in self.cc_flags:
      m.add_parameter(manipulator.EnumParameter(flag, ['on', 'off', 'default']))
    for param in self.cc_params:
      defaults = self.cc_param_defaults[param]
      if defaults['max'] <= defaults['min']:
        defaults['max'] = float('inf')
      defaults['max'] = min(defaults['max'],
                            max(1, defaults['default']) * args.scaler)
      defaults['min'] = max(defaults['min'],
                            max(1, defaults['default']) / args.scaler)

      if param == 'l1-cache-line-size':
        # gcc requires this to be a power of two or it internal errors
        m.add_parameter(manipulator.PowerOfTwoParameter(param, 4, 256))
      elif defaults['max'] > 128:
        m.add_parameter(manipulator.LogIntegerParameter(
          param, defaults['min'], defaults['max']))
      else:
        m.add_parameter(manipulator.IntegerParameter(
          param, defaults['min'], defaults['max']))

    return m

  def cfg_to_flags(self, cfg):
    flags = ['-O%d' % cfg['-O']] #'-march=native'
    for flag in self.cc_flags:
      if cfg[flag] == 'on':
        flags.append(flag)
      elif cfg[flag] == 'off' and flag[2:5] != 'no-':
        flags.append('-fno-' + flag[2:])
      elif cfg[flag] == 'off' and flag[2:5] == 'no-':
        flags.append('-f' + flag[5:])

    for param in self.cc_params:
      flags.append('--param=%s=%d' % (param, cfg[param]))

    # workaround sets of flags that trigger compiler crashes/hangs
    for bugset in self.cc_bugs:
      if len(set(bugset) & set(flags)) == len(bugset):
        flags.remove(bugset[-1])
    return flags

  def make_command(self, cfg):
    return args.compile_template.format(source=args.source, output=args.output,
                                        flags=' '.join(self.cfg_to_flags(cfg)))

  def get_tmpdir(self, result_id):
    return './tmp/%d' % result_id

  def cleanup(self, result_id):
    tmp_dir = self.get_tmpdir(result_id)
    shutil.rmtree(tmp_dir)

  def run(self, desired_result, input, limit):
    pass

  compile_results = {
    'ok': 0,
    'timeout': 1,
    'error': 2,
  }

  def run_precompiled(self, desired_result, input, limit, compile_result, result_id):
    # Make sure compile was successful
    if compile_result == self.compile_results['timeout']:
      return Result(state='TIMEOUT', time=float('inf'))
    elif compile_result == self.compile_results['error']:
      return Result(state='ERROR', time=float('inf'))

    tmp_dir = self.get_tmpdir(result_id)
    output_dir = '%s/%s' % (tmp_dir, args.output)
    try:
      run_result = self.call_program([output_dir], limit=limit,
                                     memory_limit=args.memory_limit)
    except OSError:
      return Result(state='ERROR', time=float('inf'))

    if run_result['returncode'] != 0:
      if run_result['timeout']:
        return Result(state='TIMEOUT', time=float('inf'))
      else:
        log.error('program error')
        return Result(state='ERROR', time=float('inf'))

    return Result(time=run_result['time'])

  def debug_gcc_error(self, flags):
    def fails(flags):
      cmd = args.compile_template.format(source=args.source, output=args.output,
                                         flags=' '.join(tmpflags))
      compile_result = self.call_program(cmd, limit=args.compile_limit)
      return compile_result['returncode'] != 0
    if self.args.debug:
      while len(flags) > 8:
        log.error("compile error with %d flags, diagnosing...", len(flags))
        tmpflags = filter(lambda x: random.choice((True, False)), flags)
        if fails(tmpflags):
          flags = tmpflags

      # linear scan
      minimal_flags = []
      for i in xrange(len(flags)):
        tmpflags = minimal_flags + flags[i+1:]
        if not fails(tmpflags):
          minimal_flags.append(flags[i])
      log.error("compiler crashes/hangs with flags: %s", minimal_flags)

  def compile(self, config_data, result_id):
    flags = self.cfg_to_flags(config_data)
    return self.compile_with_flags(flags, result_id)

  def compile_with_flags(self, flags, result_id):
    tmp_dir = self.get_tmpdir(result_id)
    try:
      os.stat(tmp_dir)
    except:
      os.mkdir(tmp_dir)
    output_dir = '%s/%s' % (tmp_dir, args.output)
    cmd = args.compile_template.format(source=args.source, output=output_dir,
                                        flags=' '.join(flags))

    compile_result = self.call_program(cmd, limit=args.compile_limit,
                                       memory_limit=args.memory_limit)
    if compile_result['returncode'] != 0:
      if compile_result['timeout']:
        log.warning("gcc timeout")
        return self.compile_results['timeout']
      else:
        log.warning("gcc error %s", compile_result['stderr'])
        self.debug_gcc_error(flags)
        return self.compile_results['error']
    return self.compile_results['ok']

  def save_final_config(self, configuration):
    """called at the end of tuning"""
    print "Best flags:"
    print self.make_command(configuration.data)

  def prefix_hook(self, session):
    if self.args.flags_histogram:
      counter = collections.Counter()
      q = session.query(TuningRun).filter_by(state='COMPLETE')
      total = q.count()
      for tr in q:
        print tr.program.name
        for flag in self.cfg_to_flags(tr.final_config.data):
          counter[flag] += 1.0 / total
      print counter.most_common(20)
      sys.exit(0)


if __name__ == '__main__':
  opentuner.init_logging()
  args = argparser.parse_args()
  GccFlagsTuner.main(args)
