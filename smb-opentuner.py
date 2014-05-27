#!/usr/bin/python
import adddeps #fix sys.path
import tempfile
import shutil
import subprocess
import re

import opentuner
from opentuner.search.manipulator import ConfigurationManipulator, IntegerParameter, BooleanParameter
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager
from opentuner.tuningrunmain import TuningRunMain
from opentuner.search.objective import MinimizeTime

class SMBMI(MeasurementInterface):
	def __init__(self, args):
		super(SMBMI, self).__init__(args)

	def manipulator(self):
		m = ConfigurationManipulator()
		for i in xrange(0, 10000):
			m.add_parameter(BooleanParameter("L"+str(i)))
			m.add_parameter(BooleanParameter("R"+str(i)))
			m.add_parameter(BooleanParameter("D"+str(i)))
			m.add_parameter(BooleanParameter("A"+str(i)))
			m.add_parameter(BooleanParameter("B"+str(i)))
			m.add_parameter(IntegerParameter("duration"+str(i), 1, 60))
		return m

	def run(self, desired_result, input, limit):
		cfg = desired_result.configuration.data
		with tempfile.NamedTemporaryFile(suffix=".fm2", delete=False) as f:
			with open('template.fm2') as f2:
				shutil.copyfileobj(f2, f)
			for i in xrange(0, 10000):
				line = ('|0|' +
					('R' if cfg['R'+str(i)] else '.') +
					('L' if cfg['L'+str(i)] else '.') +
					('D' if cfg['D'+str(i)] else '.') +
					'...' +
					('B' if cfg['B'+str(i)] else '.') +
					('A' if cfg['A'+str(i)] else '.') +
					'|........||\n')
				for d in xrange(0, cfg['duration'+str(i)]):
					f.write(line)
			f.flush()
			
			(stdout, stderr) = subprocess.Popen(["fceux", "--playmov", f.name, "--loadlua", "fceux-hook.lua", "smb.nes"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
		
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

