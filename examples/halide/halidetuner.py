#!/usr/bin/env python
#
# Example of synthesizing Halide schedules using OpenTuner.  This program
# expects a compiled version of Halide to exist at ~/Halide or at the location
# specified by --halide-dir.
#
# Halide programs must be modified by:
#  1) Inserting AUTOTUNE_HOOK(Func) directly after the algorithm definition
#     in main()
#  2) Creating a settings file that describes the functions and variables
#     (see apps/halide_blur.settings for an example)
#
# Halide can be found here: https://github.com/halide/Halide
#

import adddeps  # fix sys.path

import argparse
import hashlib
import itertools
import json
import logging
import math
import os
import re
import subprocess
import tempfile

from cStringIO import StringIO

import opentuner
from opentuner.search.manipulator import ConfigurationManipulator
from opentuner.search.manipulator import EnumParameter
from opentuner.search.manipulator import IntegerParameter
from opentuner.search.manipulator import PowerOfTwoParameter
from opentuner.search.manipulator import PermutationParameter
from opentuner.search.manipulator import ScheduleParameter

from opentuner.search import evolutionarytechniques
from opentuner.search import differentialevolution
from opentuner.search import simplextechniques
from opentuner.search import patternsearch
from opentuner.search import bandittechniques
from opentuner.search import technique 


GCC_CMD = ('{args.cxx} "{cpp}" -o "{bin}" -I "{args.halide_dir}/include" '
           '"{args.halide_dir}/bin/libHalide.a" -ldl -lpthread {args.cxxflags}'
           '-DAUTOTUNE_N="{args.input_size}" -DAUTOTUNE_TRIALS={args.trials}')

log = logging.getLogger('halide')

parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('source', help='Halide source file annotated with '
                                   'AUTOTUNE_HOOK')
parser.add_argument('--halide-dir', default=os.path.expanduser('~/Halide'),
                    help='Installation directory for Halide')
parser.add_argument('--input-size',
                    help='Input size to test with')
parser.add_argument('--trials', default=3, type=int,
                    help='Number of times to test each schedule')
parser.add_argument('--nesting', default=4, type=int,
                    help='Maximum depth for generated loops')
parser.add_argument('--max-split-factor', default=16, type=int)
parser.add_argument('--compile-command', default=GCC_CMD)
parser.add_argument('--cxx', default='clang++')
parser.add_argument('--cxxflags', default='')
parser.add_argument('--tmp-dir', default='/run/shm'
                    if os.access('/run/shm', os.W_OK) else '/tmp')
parser.add_argument('--settings-file')
parser.add_argument('--random-test', action='store_true')
parser.add_argument('--debug-error')
parser.add_argument('--limit', type=float, default=60)
parser.add_argument('--memory-limit', type=int, default=1024**3)


class ForType:
  SERIAL = 'Serial'
  PARALLEL = 'Parallel'
  VECTORIZED = 'Vectorized'
  UNROLLED = 'Unrolled'
  # Legal choices for inner and outer loops:
  _OUTER = [SERIAL, PARALLEL]
  _INNER = [SERIAL, VECTORIZED, UNROLLED]


class LoopLevel:
  INLINE = ''
  ROOT = '<root>'
  PARENT = '<parent>'

class HalideRandomConfig(opentuner.search.technique.SearchTechnique):
  def desired_configuration(self):
    '''
    inject random configs with no compute_at() calls to kickstart the search process
    '''
    cfg = self.manipulator.random()
    for k in cfg.keys():
      if re.match('.*_compute_level', k):
        cfg[k] = LoopLevel.INLINE
    return cfg

technique.register(bandittechniques.AUCBanditMetaTechnique([
        HalideRandomConfig(),
        differentialevolution.DifferentialEvolutionAlt(),
        evolutionarytechniques.UniformGreedyMutation(),
        evolutionarytechniques.NormalGreedyMutation(mutation_rate=0.3),
      ], name = "HalideMetaTechnique"))

class HalideTuner(opentuner.measurement.MeasurementInterface):

  def __init__(self, args):
    args.technique = ['HalideMetaTechnique']
    super(HalideTuner, self).__init__(args, program_name=args.source)
    timing_prefix = open(os.path.join(os.path.dirname(__file__),
                                      'timing_prefix.h')).read()
    self.template = timing_prefix + open(args.source).read()
    if not args.settings_file:
      args.settings_file = os.path.splitext(args.source)[0] + '.settings'
    with open(args.settings_file) as fd:
      self.settings = json.load(fd)
    if not args.input_size:
      args.input_size = self.settings['input_size']
    self.min_collection_cost = float('inf')

  def manipulator(self):
    """
    The definition of the manipulator is meant to mimic the Halide::Schedule
    data structure and defines the configuration space to search
    """
    manipulator = HalideConfigurationManipulator(self)
    compute_at_choices = [LoopLevel.INLINE, LoopLevel.ROOT]
    for func in self.settings['functions']:
      compute_at_choices.extend(
        (func['name'], var, level)
        for var, level in itertools.product(func['vars'], xrange(args.nesting)))

    for func in self.settings['functions']:
      name = func['name']
      # TODO(jansel): add storage locations other than INLINE/ROOT (these
      #              seemed to cause lots of errors)
      manipulator.add_parameter(EnumParameter(
        '{0}_store_level'.format(name),
        [LoopLevel.INLINE, LoopLevel.ROOT, LoopLevel.PARENT]))
      manipulator.add_parameter(EnumParameter(
        '{0}_compute_level'.format(name), compute_at_choices))

      manipulator.add_parameter(PermutationParameter(
        '{0}_store_order'.format(name), func['vars']))

      sched_vars = []
      sched_deps = dict()
      for var in func['vars']:
        sched_vars.append((var, 0))
        for i in xrange(1, self.args.nesting):
          sched_vars.append((var, i))
          sched_deps[(var, i-1)] = [(var, i)]
      manipulator.add_parameter(ScheduleParameter(
        '{0}_compute_order'.format(name), sched_vars, sched_deps))

      for var in func['vars']:
        manipulator.add_parameter(EnumParameter(
          '{0}_var_{1}_{2}'.format(name, 0, var), ForType._OUTER))

        for nesting in xrange(1, self.args.nesting):
          manipulator.add_parameter(EnumParameter(
            '{0}_var_{1}_{2}'.format(name, nesting, var), ForType._INNER))
          manipulator.add_parameter(PowerOfTwoParameter(
            '{0}_splitfactor_{1}_{2}'.format(name, nesting, var),
            1, args.max_split_factor))

      # TODO(jansel): add bounds (is it needed?)
    return manipulator

  def resolve_compute_level(self, cfg, var_names, name, var, nesting, seen=None):
    if seen is None:
      seen = set()

    while (name, var, nesting) not in var_names:
      nesting -= 1
      assert nesting >= 0

    if (name, var, nesting) in seen:
      # cycle detected
      order = [f['name'] for f in self.settings['functions']]
      return sorted(seen, key=lambda x: order.index(x[0]))[-1]
    seen.add((name, var, nesting))

    compute_level_recursive = cfg['{0}_compute_level'.format(name)]
    if compute_level_recursive not in (LoopLevel.INLINE, LoopLevel.ROOT):
      return self.resolve_compute_level(cfg, var_names, *compute_level_recursive, seen=seen)

    return name, var, nesting

  def cfg_to_schedule(self, cfg):
    """
    Produce a Halide schedule from a configuration dictionary
    """
    o = StringIO()
    cnt = 0
    temp_vars = list()

    # build list of all used variable names
    var_names = dict()
    for func in self.settings['functions']:
      name = func['name']
      for var in func['vars']:
        var_names[(name, var, 0)] = var
        for nesting in xrange(1, self.args.nesting):
          split_factor = cfg.get('{0}_splitfactor_{1}_{2}'.format(
            name, nesting, var), 0)
          if split_factor > 1 and (name, var, nesting - 1) in var_names:
            var_names[(name, var, nesting)] = '_{var}{cnt}'.format(
              func=name, var=var, nesting=nesting, cnt=cnt)
            temp_vars.append(var_names[(name, var, nesting)])
          cnt += 1

    for func in self.settings['functions']:
      name = func['name']
      store_level = cfg['{0}_store_level'.format(name)]
      store_order = cfg['{0}_store_order'.format(name)]
      compute_level = cfg['{0}_compute_level'.format(name)]
      compute_order = cfg['{0}_compute_order'.format(name)]

      print >>o, name,

      # compute_at options
      used_compute_at = False
      if compute_level == LoopLevel.INLINE:
        pass
      elif compute_level == LoopLevel.ROOT:
        print >>o, '.compute_root()',
      else:
        compute_level = self.resolve_compute_level(
          cfg, var_names, *compute_level)
        if compute_level and compute_level[0] != name:
          used_compute_at = True
          print >>o, '.compute_at(%s, %s)' % (
            compute_level[0], var_names[compute_level])
        else:
          compute_level = LoopLevel.INLINE

      # store_at options
      if store_level == LoopLevel.INLINE or compute_level == LoopLevel.INLINE:
        pass
      elif store_level == LoopLevel.ROOT or compute_level == LoopLevel.ROOT:
        print >>o, '.store_root()',
      elif store_level == LoopLevel.PARENT and used_compute_at:
        f, v, n = compute_level
        store_level = (f, v, max(0, n - 1))
        print >>o, '.store_at(%s, %s)' % (
          store_level[0], var_names[store_level])

      # reorder_storage
      print >>o, '.reorder_storage({0})'.format(', '.join(store_order))

      vectorize_used = False
      for var in func['vars']:
        lastvarname = None

        # handle all splits
        for nesting in xrange(1, self.args.nesting):
          split_factor = cfg.get('{0}_splitfactor_{1}_{2}'.format(
            name, nesting, var), 0)
          if split_factor <= 1:
            break

          for nesting2 in xrange(nesting+1, self.args.nesting):
            split_factor2 = cfg.get('{0}_splitfactor_{1}_{2}'.format(
              name, nesting2, var), 0)
            if split_factor2 <= 1:
              break
            split_factor *= split_factor2

          varname = var_names[(name, var, nesting)]
          lastvarname = var_names[(name, var, nesting - 1)]
          print >>o, '.split({0}, {0}, {1}, {2})'.format(
            lastvarname, varname, split_factor),

        # handle ForType of each variable
        for nesting in xrange(self.args.nesting):
          for_type = cfg['{0}_var_{1}_{2}'.format(name, nesting, var)]
          try:
            varname = var_names[(name, var, nesting)]
          except:
            break  # nesting level not used
          if for_type == ForType.SERIAL:
            print >>o, '/*.serial(%s)*/' % varname,
          elif for_type == ForType.PARALLEL:
            print >>o, '.parallel(%s)' % varname,
          elif for_type == ForType.VECTORIZED and not vectorize_used:
            vectorize_used = True
            # TODO(jansel): add validator to make only 1 vectorize call
            print >>o, '.vectorize(%s)' % varname,
          elif for_type == ForType.UNROLLED:
            print >>o, '.unroll(%s)' % varname,
        print >>o

      # drop unused variables and truncate (Halide supports only 5 reorders)
      compute_order_vars = [var_names[(name, v, n)] for v, n in compute_order
                            if (name, v, n) in var_names][:5]
      print >>o, '.reorder({0})'.format(', '.join(compute_order_vars))
      print >>o, ';'

    if temp_vars:
      return 'Halide::Var {0};\n{1}'.format(
        ', '.join(temp_vars), o.getvalue())
    else:
      return o.getvalue()

  def run_schedule(self, schedule):
    """
    Generate a temporary Halide cpp file with schedule inserted and run it
    with our timing harness found in timing_prefix.h.
    """
    def repl_autotune_hook(match):
      return '\n\n%s\n\n_autotune_timing_stub(%s);' % (
        schedule, match.group(1))
    source = re.sub(r'\n\s*AUTOTUNE_HOOK\(\s*([a-zA-Z0-9_]+)\s*\)',
                    repl_autotune_hook, self.template)
    return self.run_source(source)

  def run_baseline(self):
    """
    Generate a temporary Halide cpp file with schedule inserted and run it
    with our timing harness found in timing_prefix.h.
    """
    def repl_autotune_hook(match):
      return '\n\n_autotune_timing_stub(%s);' % match.group(1)
    source = re.sub(r'\n\s*BASELINE_HOOK\(\s*([a-zA-Z0-9_]+)\s*\)',
                    repl_autotune_hook, self.template)
    return self.run_source(source)

  def run_source(self, source):
    with tempfile.NamedTemporaryFile(suffix='.cpp', prefix='halide',
                                     dir=args.tmp_dir) as cppfile:
      cppfile.write(source)
      cppfile.flush()
      #binfile = os.path.splitext(cppfile.name)[0] + '.bin'
      binfile = '/tmp/halide.bin'
      cmd = args.compile_command.format(
        cpp=cppfile.name, bin=binfile, args=args)
      compile_result = self.call_program(cmd, limit=args.limit,
                                 memory_limit=args.memory_limit)
      if compile_result['returncode'] != 0:
        log.error("compile failed: %s", compile_result)
        return None

    try:
      result = self.call_program(binfile,
                                 limit=1 + 2 * self.min_collection_cost,
                                 memory_limit=args.memory_limit)
      stdout = result['stdout']
      stderr = result['stderr']
      returncode = result['returncode']

      if returncode != 0 or stderr:
        log.error('invalid schedule: %s', stderr.strip())
        if args.debug_error and args.debug_error in stderr:
          open('/tmp/halideerror.cpp', 'w').write(source)
          raw_input(
            'offending schedule written to /tmp/halideerror.cpp, press ENTER to continue')
        return None
      elif result['timeout']:
        log.info('timeout: collection cost %.2f + %.2f',
                 compile_result['time'], result['time'])
        return float('inf')
      else:
        try:
          time = json.loads(stdout)['time']
        except:
          log.exception("error parsing output: %s", result)
          return None
        log.info('success: %.4f (collection cost %.2f + %.2f)',
                 time, compile_result['time'], result['time'])
        self.min_collection_cost = min(self.min_collection_cost, result['time'])
        return time
    finally:
      os.unlink(binfile)

  def run_cfg(self, cfg):
    return self.run_schedule(self.cfg_to_schedule(cfg))

  def run(self, desired_result, input, limit):
    time = self.run_cfg(desired_result.configuration.data)
    if time is not None:
      return opentuner.resultsdb.models.Result(time=time)
    else:
      return opentuner.resultsdb.models.Result(state='ERROR',
                                               time=float('inf'))

  def save_final_config(self, configuration):
    """called at the end of tuning"""
    print 'Final Configuration:'
    print self.cfg_to_schedule(configuration.data)


class HalideConfigurationManipulator(ConfigurationManipulator):

  def __init__(self, halide_tuner):
    super(HalideConfigurationManipulator, self).__init__()
    self.halide_tuner = halide_tuner

  def hash_config(self, config):
    """
    Multiple configs can lead to the same schedule, so we provide a custom
    hash function that hashes the resulting schedule instead of the raw config.
    This will lead to fewer duplicate tests.
    """
    schedule = self.halide_tuner.cfg_to_schedule(config)
    return hashlib.sha256(schedule).hexdigest()


def random_test(args):
  from pprint import pprint
  opentuner.tuningrunmain.init_logging()
  m = HalideTuner(args)
  cfg = m.manipulator().random()
  pprint(cfg)
  print
  schedule = m.cfg_to_schedule(cfg)
  print schedule
  print
  print 'Schedule', m.run_schedule(schedule)
  print 'Baseline', m.run_baseline()

if __name__ == '__main__':
  args = parser.parse_args()
  if args.random_test:
    random_test(args)
  else:
    HalideTuner.main(args)
