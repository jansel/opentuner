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
		with tempfile.NamedTemporaryFile(suffix=".fm2", delete=True) as f:
			with open('template.fm2') as f2:
				shutil.copyfileobj(f2, f)
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

			for i in xrange(0, 400*60):
				line = ('|0|' +
					('R' if i in right else '.') +
					('L' if i in left else '.') +
					('D' if False else '.') +
					'...' +
					('B' if i in running else '.') +
					('A' if i in jumping else '.') +
					'|........||\n')
				f.write(line)
			f.flush()
			
			(stdout, stderr) = subprocess.Popen(["fceux", "--playmov", f.name, "--loadlua", "fceux-hook.lua", "--volume", "0", "smb.nes"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
		
		match = re.search(r"^died (\d+)$", stdout, re.MULTILINE)
		if match:
			print match.group(0)
			return opentuner.resultsdb.models.Result(state='OK', time=-float(match.group(1)))
		match = re.search(r"^won (\d+)$", stdout, re.MULTILINE)
		if match:
			print match.group(0)
			return opentuner.resultsdb.models.Result(state='OK', time=-float(match.group(1))*10000)
		#error?
		print stderr
		print stdout
		return opentuner.resultsdb.models.Result(state='ERROR', time=float('inf'))

if __name__ == '__main__':
	argparser = opentuner.default_argparser()
	SMBMI.main(argparser.parse_args())

