#!/usr/bin/python

"""OpenTuner plays Super Mario Bros. for NES

We write a movie file and ask the emulator to play it back while running
fceux-hook.lua, which checks for death/flagpole and prints the fitness to
stdout where OpenTuner, as the parent process, can read it.
"""

import adddeps #fix sys.path
import argparse
import base64
import pickle
import tempfile
import shutil
import subprocess
import re

import opentuner
from opentuner.search.manipulator import ConfigurationManipulator, IntegerParameter, EnumParameter, BooleanParameter
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager
from opentuner.tuningrunmain import TuningRunMain
from opentuner.search.objective import MinimizeTime

argparser = argparse.ArgumentParser(parents=opentuner.argparsers())
argparser.add_argument('--tuning-run', help='concatenate new bests from given tuning run into single movie')
argparser.add_argument('--headful', action='store_true', help='run headful (not headless) for debugging or live demo')
argparser.add_argument('--xvfb-delay', type=int, default=0, help='delay between launching xvfb and fceux')
argparser.add_argument('--fceux-path', default='fceux', help='path to fceux executable')

# Functions for building FCEUX movie files (.fm2 files)

def fm2_line(up, down, left, right, a, b, start, select, reset=False):
  """formats one frame of input with the given button presses"""
  return ''.join(('|1|' if reset else '|0|') +
    ('R' if right else '.') +
    ('L' if left else '.') +
    ('D' if down else '.') +
    ('U' if up else '.') +
    ('T' if start else '.') +
    ('D' if select else '.') +
    ('B' if b else '.') +
    ('A' if a else '.') +
    '|........||')

def maxd(iterable, default):
  try:
    return max(iterable)
  except ValueError:
    return default

def fm2_lines(up, down, left, right, a, b, start, select, reset=set(), minFrame=None, maxFrame=None):
  """formats many frames using the given button-press sets"""
  if minFrame is None:
    minFrame = 0
  if maxFrame is None:
    maxFrame = max(maxd(up, 0), maxd(down, 0), maxd(left, 0), maxd(right, 0), maxd(a, 0), maxd(b, 0), maxd(start, 0), maxd(select, 0), maxd(reset, 0)) + 1
  lines = list()
  for i in xrange(minFrame, maxFrame):
    lines.append(fm2_line(i in up, i in down, i in left, i in right, i in a, i in b, i in start, i in select, i in reset))
  return lines

def fm2_smb_header():
  return ["version 3",
    "emuVersion 9828",
    "romFilename smb.nes",
    "romChecksum base64:jjYwGG411HcjG/j9UOVM3Q==",
    "guid 51473540-E9D7-11E3-ADFC-46CE3219C4E0",
    "fourscore 0",
    "port0 1",
    "port1 1",
    "port2 0"]

def fm2_smb(left, right, down, b, a, header=True, padding=True, minFrame=None, maxFrame=None):
  reset = set()
  start = set()
  if padding:
    left = set([x+196 for x in left])
    right = set([x+196 for x in right])
    down = set([x+196 for x in down])
    b = set([x+196 for x in b])
    a = set([x+196 for x in a])
    reset.add(0)
    start.add(33)
  lines = fm2_lines(set(), down, left, right, a, b, start, set(), reset, minFrame, maxFrame)
  if header:
    return "\n".join(fm2_smb_header() + lines)
  else:
    return "\n".join(lines)

def run_movie(fm2, args):
  with tempfile.NamedTemporaryFile(suffix=".fm2", delete=True) as f:
    f.write(fm2)
    f.flush()
    cmd = []
    if not args.headful:
      cmd += ["xvfb-run", "-a", "-w", str(args.xvfb_delay)]
    cmd += [args.fceux_path, "--playmov", f.name, "--loadlua",
        "fceux-hook.lua", "--nogui", "--volume", "0", "smb.nes"]
    stdout, stderr = subprocess.Popen(cmd, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate()
  match = re.search(r"^(won|died) (\d+) (\d+)$", stdout, re.MULTILINE)
  if not match:
    print stderr
    print stdout
    raise ValueError
  wl = match.group(1)
  x_pos = int(match.group(2))
  framecount = int(match.group(3))
  return (wl, x_pos, framecount)

# logically part of SMBMI as it's coupled to the parameterization
def interpret_cfg(cfg):
  right = set()
  left = set()
  down = set()
  running = set()
  start = 0
  for i in xrange(0, 1000):
    move = cfg['move{}'.format(i)]
    move_duration = cfg['move_duration{}'.format(i)]
    if "R" in move:
      right.update(xrange(start, start + move_duration))
    if "L" in move:
      left.update(xrange(start, start + move_duration))
    if "B" in move:
      running.update(xrange(start, start + move_duration))
    start += move_duration
  jumping = set()
  for i in xrange(0, 1000):
    jump_frame = cfg['jump_frame{}'.format(i)]
    jump_duration = cfg['jump_duration{}'.format(i)]
    jumping.update(xrange(jump_frame, jump_frame + jump_duration))
  return left, right, down, running, jumping

class SMBMI(MeasurementInterface):
  def __init__(self, args):
    super(SMBMI, self).__init__(args)
    self.parallel_compile = True
    self.args = args

  def manipulator(self):
    m = ConfigurationManipulator()
    for i in xrange(0, 1000):
      m.add_parameter(EnumParameter('move{}'.format(i), ["R", "L", "RB", "LB", "N", "LR", "LRB", "R2", "RB2", "R3", "RB3"]))
      m.add_parameter(IntegerParameter('move_duration{}'.format(i), 1, 60))
      #m.add_parameter(BooleanParameter("D"+str(i)))
    for i in xrange(0, 1000):
      m.add_parameter(IntegerParameter('jump_frame{}'.format(i), 0, 24000))
      m.add_parameter(IntegerParameter('jump_duration{}'.format(i), 1, 32))
    return m

  def compile(self, cfg, id):
    left, right, down, running, jumping = interpret_cfg(cfg)
    fm2 = fm2_smb(left, right, down, running, jumping)
    try:
      wl, x_pos, framecount = run_movie(fm2, self.args)
    except ValueError:
      return opentuner.resultsdb.models.Result(state='ERROR', time=float('inf'))
    print wl, x_pos, framecount
    if "died" in wl:
      return opentuner.resultsdb.models.Result(state='OK', time=-float(x_pos))
    else:
      #add fitness for frames remaining on timer
      #TODO: this results in a large discontinuity; is that right?
      return opentuner.resultsdb.models.Result(state='OK', time=-float(x_pos + 400*60 - framecount))

  def run_precompiled(self, desired_result, input, limit, compile_result, id):
    return compile_result

  def run(self, desired_result, input, limit):
    pass

def new_bests_movie(args):
  (stdout, stderr) = subprocess.Popen(["sqlite3", args.database, "select configuration_id from result where tuning_run_id = %d and was_new_best = 1 order by collection_date;" % args.tuning_run], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
  cids = stdout.split()
  print '\n'.join(fm2_smb_header())
  for cid in cids:
    (stdout, stderr) = subprocess.Popen(["sqlite3", args.database, "select quote(data) from configuration where id = %d;" % int(cid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    cfg = pickle.loads(base64.b16decode(stdout.strip()[2:-1]))
    left, right, down, running, jumping = interpret_cfg(cfg)
    fm2 = fm2_smb(left, right, down, running, jumping)
    _, _, framecount = run_movie(fm2, args)
    print fm2_smb(left, right, down, running, jumping, header=False, maxFrame=framecount)

if __name__ == '__main__':
  args = argparser.parse_args()
  if args.tuning_run:
    if args.database is not None:
      new_bests_movie(args)
    else:
      print "must specify --database"
  else:
    SMBMI.main(args)

