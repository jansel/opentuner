#!/usr/bin/python
import adddeps #fix sys.path
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

def fm2_line(up, down, left, right, a, b, start, select, reset=False):
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
		"port0 1",
		"port1 1",
		"port2 0"]

def fm2_smb(left, right, down, b, a, header=True, padding=True):
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
	lines = fm2_lines(set(), down, left, right, a, b, start, set(), reset)
	if header:
		return "\n".join(fm2_smb_header() + lines)
	else:
		return "\n".join(lines)

class SMBMI(MeasurementInterface):
	def __init__(self, args):
		super(SMBMI, self).__init__(args)

	def manipulator(self):
		m = ConfigurationManipulator()
		for i in xrange(0, 1000):
			m.add_parameter(EnumParameter("move"+str(i), ["R", "L", "RB", "LB", "N", "LR", "LRB", "R2", "RB2", "R3", "RB3"]))
			m.add_parameter(IntegerParameter("move_duration"+str(i), 1, 60))
			#m.add_parameter(BooleanParameter("D"+str(i)))
		for i in xrange(0, 1000):
			m.add_parameter(IntegerParameter("jump_frame"+str(i), 0, 24000))
			m.add_parameter(IntegerParameter("jump_duration"+str(i), 1, 32))
		return m

	def run(self, desired_result, input, limit):
		cfg = desired_result.configuration.data
		jumping = set()
		for i in xrange(0, 1000):
			jump_frame = cfg["jump_frame"+str(i)]
			jump_duration = cfg["jump_duration"+str(i)]
			jumping.update(xrange(jump_frame, jump_frame + jump_duration))
		right = set()
		left = set()
		running = set()
		start = 0
		for i in xrange(0, 1000):
			move = cfg["move"+str(i)]
			move_duration = cfg["move_duration"+str(i)]
			if "R" in move:
				right.update(xrange(start, start + move_duration))
			if "L" in move:
				left.update(xrange(start, start + move_duration))
			if "B" in move:
				running.update(xrange(start, start + move_duration))
			start += move_duration

		with tempfile.NamedTemporaryFile(suffix=".fm2", delete=True) as f:
			f.write(fm2_smb(left, right, set(), running, jumping))
			f.flush()
			(stdout, stderr) = subprocess.Popen(["fceux", "--playmov", f.name, "--loadlua", "fceux-hook.lua", "--volume", "0", "smb.nes"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
		
		match = re.search(r"^(won|died) (\d+) (\d+)$", stdout, re.MULTILINE)
		if not match:
			print stderr
			print stdout
			return opentuner.resultsdb.models.Result(state='ERROR', time=float('inf'))
		print match.group(0)
		wl = match.group(1)
		x_pos = int(match.group(2))
		framecount = int(match.group(3))
		if "died" in wl:
			return opentuner.resultsdb.models.Result(state='OK', time=-float(x_pos))
		else:
			#add fitness for frames remaining on timer
			#TODO: this results in a large discontinuity; is that right?
			return opentuner.resultsdb.models.Result(state='OK', time=-float(x_pos + 400*60 - framecount))

if __name__ == '__main__':
	argparser = opentuner.default_argparser()
	SMBMI.main(argparser.parse_args())

