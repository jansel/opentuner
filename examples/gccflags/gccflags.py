#!/usr/bin/env python
import adddeps  # fix sys.path

import math
import argparse
import ast
import collections
import json
import logging
import opentuner
import os
import random
import re
import shutil
import subprocess
import sys

from opentuner.resultsdb.models import Result, TuningRun
from opentuner.search import manipulator

FLAGS_WORKING_CACHE_FILE = 'cc_flags.json'
PARAMS_DEFAULTS_CACHE_FILE = 'cc_param_defaults.json'
PARAMS_DEF_PATH = '~/gcc-4.9.0/gcc/params.def'
PARAMS_WORKING_CACHE_FILE = 'cc_params.json'

log = logging.getLogger('gccflags')

argparser = argparse.ArgumentParser(parents=opentuner.argparsers())
argparser.add_argument('source', help='source file to compile')
argparser.add_argument('--compile-template',
                       default='{cc} {source} -o {output} -lpthread {flags}',
                       help='command to compile {source} into {output} with'
                            ' {flags}')
argparser.add_argument('--compile-limit', type=float, default=30,
                       help='kill gcc if it runs more than {default} sec')
argparser.add_argument('--scaler', type=int, default=4,
                       help='by what factor to try increasing parameters')
argparser.add_argument('--cc', default='g++', help='g++ or gcc')
argparser.add_argument('--output', default='./tmp.bin',
                       help='temporary file for compiler to write to')
argparser.add_argument('--debug', action='store_true',
                       help='on gcc errors try to find minimal set '
                            'of args to reproduce error')
argparser.add_argument('--force-killall', action='store_true',
                       help='killall cc1plus before each collection')
argparser.add_argument('--memory-limit', default=1024 ** 3, type=int,
                       help='memory limit for child process')
argparser.add_argument('--no-cached-flags', action='store_true',
                       help='regenerate the lists of legal flags each time')
argparser.add_argument('--flags-histogram', action='store_true',
                       help='print out a histogram of flags')
argparser.add_argument('--flag-importance',
                       help='Test the importance of different flags from a '
                            'given json file.')


class GccFlagsTuner(opentuner.measurement.MeasurementInterface):
  def __init__(self, *pargs, **kwargs):
    super(GccFlagsTuner, self).__init__(program_name=args.source, *pargs,
                                        **kwargs)
    self.gcc_version = self.extract_gcc_version()
    self.cc_flags = self.extract_working_flags()
    self.cc_param_defaults = self.extract_param_defaults()
    self.cc_params = self.extract_working_params()

    # these bugs are hardcoded for now
    # sets of options which causes gcc to barf
    if True:
      # These bugs were for gcc 4.7 on ubuntu
      self.cc_bugs = (['-fipa-matrix-reorg', '-fwhole-program'],
                      ['-fno-tree-coalesce-inlined-vars'],
                      ['-fno-inline-atomics'],
                      ['-ftoplevel-reorder', '-fno-unit-at-a-time'])
    else:
      # Bugs for gcc 4.9 (work in progress, incomplete list)
      self.cc_bugs = (['-ftoplevel-reorder', '-fno-unit-at-a-time'], )

    self.result_list = {}
    self.parallel_compile = True
    try:
      os.stat('./tmp')
    except OSError:
      os.mkdir('./tmp')
    self.run_baselines()

  def run_baselines(self):
    log.info("baseline perfs -O0=%.4f -O1=%.4f -O2=%.4f -O3=%.4f",
             *[self.run_with_flags(['-O%d' % i], None).time
               for i in range(4)])

  def extract_gcc_version(self):
    m = re.search(r'([0-9]+)[.]([0-9]+)[.]([0-9]+)', subprocess.check_output([
        self.args.cc, '--version']))
    if m:
      gcc_version = tuple(map(int, m.group(1, 2, 3)))
    else:
      gcc_version = None
    log.debug('gcc version %s', gcc_version)
    return gcc_version

  def extract_working_flags(self):
    """
    Figure out which gcc flags work (don't cause gcc to barf) by running
    each one.
    """
    if os.path.isfile(FLAGS_WORKING_CACHE_FILE) and not args.no_cached_flags:
      # use cached version
      found_cc_flags = json.load(open(FLAGS_WORKING_CACHE_FILE))
    else:
      # extract flags from --help=optimizers
      optimizers, err = subprocess.Popen([self.args.cc, '--help=optimizers'],
                                         stdout=subprocess.PIPE).communicate()
      found_cc_flags = re.findall(r'^  (-f[a-z0-9-]+) ', optimizers,
                                  re.MULTILINE)
      log.info('Determining which of %s possible gcc flags work',
               len(found_cc_flags))
      found_cc_flags = filter(self.check_if_flag_works, found_cc_flags)
      json.dump(found_cc_flags, open(FLAGS_WORKING_CACHE_FILE, 'w'))
    return found_cc_flags

  def extract_param_defaults(self):
    """
    Get the default, minimum, and maximum for each gcc parameter.
    Requires source code for gcc to be in your home directory.
    This example ships with a cached version so it does not require source.
    """
    if os.path.isfile(PARAMS_DEFAULTS_CACHE_FILE) and not args.no_cached_flags:
      # use cached version
      param_defaults = json.load(open(PARAMS_DEFAULTS_CACHE_FILE))
    else:
      # default values of params need to be extracted from source code,
      # since they are not in --help
      param_defaults = dict()
      params_def = open(os.path.expanduser(PARAMS_DEF_PATH)).read()
      for m in re.finditer(r'DEFPARAM *\((([^")]|"[^"]*")*)\)', params_def):
        param_def_str = (m.group(1)
                         #  Hacks!!!
                         .replace('GGC_MIN_EXPAND_DEFAULT', '30')
                         .replace('GGC_MIN_HEAPSIZE_DEFAULT', '4096')
                         .replace('50 * 1024 * 1024', '52428800'))
        try:
          name, desc, default, param_min, param_max = ast.literal_eval(
              '[' + param_def_str.split(',', 1)[1] + ']')
          param_defaults[name] = {'default': default,
                                  'min': param_min,
                                  'max': param_max}
        except:
          log.exception("error with %s", param_def_str)
      json.dump(param_defaults, open(PARAMS_DEFAULTS_CACHE_FILE, 'w'))
    return param_defaults

  def extract_working_params(self):
    """
    Figure out which gcc params work (don't cause gcc to barf) by running
    each one to test.
    """
    params, err = subprocess.Popen(
        [self.args.cc, '--help=params'], stdout=subprocess.PIPE).communicate()
    all_params = re.findall(r'^  ([a-z0-9-]+) ', params, re.MULTILINE)
    all_params = sorted(set(all_params) &
                        set(self.cc_param_defaults.keys()))
    if os.path.isfile(PARAMS_WORKING_CACHE_FILE) and not args.no_cached_flags:
      # use cached version
      return json.load(open(PARAMS_WORKING_CACHE_FILE))
    else:
      log.info('Determining which of %s possible gcc params work',
               len(all_params))
      working_params = []
      for param in all_params:
        if self.check_if_flag_works('--param={}={}'.format(
                param, self.cc_param_defaults[param]['default'])):
          working_params.append(param)
      json.dump(working_params, open(PARAMS_WORKING_CACHE_FILE, 'w'))
      return working_params

  def check_if_flag_works(self, flag, try_inverted=True):
    cmd = args.compile_template.format(source=args.source, output=args.output,
                                       flags=flag, cc=args.cc)
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
    if try_inverted and flag[:2] == '-f':
      if not self.check_if_flag_works(invert_gcc_flag(flag),
                                      try_inverted=False):
        log.warning("Odd... %s works but %s does not", flag,
                    invert_gcc_flag(flag))
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
    flags = ['-O%d' % cfg['-O']]
    for flag in self.cc_flags:
      if cfg[flag] == 'on':
        flags.append(flag)
      elif cfg[flag] == 'off':
        flags.append(invert_gcc_flag(flag))

    for param in self.cc_params:
      flags.append('--param=%s=%d' % (param, cfg[param]))

    # workaround sets of flags that trigger compiler crashes/hangs
    for bugset in self.cc_bugs:
      if len(set(bugset) & set(flags)) == len(bugset):
        flags.remove(bugset[-1])
    return flags

  def make_command(self, cfg):
    return args.compile_template.format(source=args.source, output=args.output,
                                        flags=' '.join(self.cfg_to_flags(cfg)),
                                        cc=args.cc)

  def get_tmpdir(self, result_id):
    return './tmp/%d' % result_id

  def cleanup(self, result_id):
    tmp_dir = self.get_tmpdir(result_id)
    shutil.rmtree(tmp_dir)

  def compile_and_run(self, desired_result, input, limit):
    cfg = desired_result.configuration.data
    compile_result = self.compile(cfg, 0)
    return self.run_precompiled(desired_result, input, limit, compile_result, 0)

  compile_results = {'ok': 0, 'timeout': 1, 'error': 2}

  def run_precompiled(self, desired_result, input, limit, compile_result,
                      result_id):
    if self.args.force_killall:
      os.system('killall -9 cc1plus 2>/dev/null')
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
    def fails(subflags):
      cmd = args.compile_template.format(source=args.source, output=args.output,
                                         flags=' '.join(subflags),
                                         cc=args.cc)
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
        tmpflags = minimal_flags + flags[i + 1:]
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
    except OSError:
      os.mkdir(tmp_dir)
    output_dir = '%s/%s' % (tmp_dir, args.output)
    cmd = args.compile_template.format(source=args.source, output=output_dir,
                                       flags=' '.join(flags),
                                       cc=args.cc)

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

  def run_with_flags(self, flags, limit):
    return self.run_precompiled(None, None, limit,
                                self.compile_with_flags(flags, 0), 0)

  def save_final_config(self, configuration):
    """called at the end of tuning"""
    print "Best flags written to gccflags_final_config.{json,cmd}"
    self.manipulator().save_to_file(configuration.data,
                                    'gccflags_final_config.json')
    with open('gccflags_final_config.cmd', 'w') as fd:
      fd.write(self.make_command(configuration.data))

  def flags_histogram(self, session):
    counter = collections.Counter()
    q = session.query(TuningRun).filter_by(state='COMPLETE')
    total = q.count()
    for tr in q:
      print tr.program.name
      for flag in self.cfg_to_flags(tr.final_config.data):
        counter[flag] += 1.0 / total
    print counter.most_common(20)

  def flag_importance(self):
    """
    Test the importance of each flag by measuring the performance with that
    flag removed.  Print out a table for paper
    """
    with open(self.args.flag_importance) as fd:
      best_cfg = json.load(fd)
    flags = self.cfg_to_flags(best_cfg)
    counter = collections.Counter()
    baseline_time = self.flags_mean_time(flags)
    for flag in flags[1:]:
      delta_flags = [f for f in flags if f != flag]
      flag_time = self.flags_mean_time(delta_flags)
      impact = max(0.0, flag_time - baseline_time)
      if math.isinf(impact):
        impact = 0.0
      counter[flag] = impact
      print flag, '{:.4f}'.format(impact)
    total_impact = sum(counter.values())
    remaining_impact = total_impact
    print r'\bf Flag & \bf Importance \\\hline'
    for flag, impact in counter.most_common(20):
      print r'{} & {:.1f}\% \\\hline'.format(flag, 100.0 * impact / total_impact)
      remaining_impact -= impact
    print r'{} other flags & {:.1f}% \\\hline'.format(
      len(flags) - 20, 100.0 * remaining_impact / total_impact)

  def flags_mean_time(self, flags, trials=10):
    precompiled = self.compile_with_flags(flags, 0)
    total = 0.0
    for _ in xrange(trials):
      total += self.run_precompiled(None, None, None, precompiled, 0).time
    return total / trials

  def prefix_hook(self, session):
    if self.args.flags_histogram:
      self.flags_histogram(session)
      sys.exit(0)
    if self.args.flag_importance:
      self.flag_importance()
      sys.exit(0)



def invert_gcc_flag(flag):
  assert flag[:2] == '-f'
  if flag[2:5] != 'no-':
    return '-fno-' + flag[2:]
  return '-f' + flag[5:]


if __name__ == '__main__':
  opentuner.init_logging()
  args = argparser.parse_args()
  GccFlagsTuner.main(args)
