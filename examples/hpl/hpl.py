import adddeps #fix sys.path

import argparse
import logging

import opentuner
from opentuner.search.manipulator import (ConfigurationManipulator,
                                          IntegerParameter,
                                          FloatParameter)
from opentuner.search.objective import MinimizeTime
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager
from opentuner.tuningrunmain import TuningRunMain

log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(parents=opentuner.argparsers())

parser.add_argument('--size', type=int, default=800,
                    help='dimensions for the HPL matrix')
parser.add_argument('--nprocs', type=int, default=4,
                    help='number of processors for each HPL run (minimum=4)')
parser.add_argument('--xhpl', type=str, default="hpl-2.1/bin/OSX/xhpl",
                    help='location of xhpl binary')

class HPLinpack(MeasurementInterface):
    def run(self, desired_result, input, limit):
        self.output_hpl_datfile(desired_result.configuration.data)
        import subprocess, os
        binary = self.args.xhpl
        subprocess.call(["mpirun", "-np", str(self.args.nprocs), binary])
        
        val = self.get_time_from_hpl_output()
        
        return opentuner.resultsdb.models.Result(time=val)
        
    def manipulator(self):
        #FIXME: should some of these be expressed as booleans or switch parameters?
        #FIXME: how to express P and Q, given PxQ=nprocs, with nprocs being fixed?
        #FIXME: how to express logscaled parameter with a particular base?
        manipulator = ConfigurationManipulator()
        manipulator.add_parameter(IntegerParameter("blocksize", 1, 64))
        manipulator.add_parameter(IntegerParameter("row_or_colmajor_pmapping", 0, 1))
        manipulator.add_parameter(IntegerParameter("pfact", 0, 2))
        manipulator.add_parameter(IntegerParameter("nbmin", 1, 4))
        manipulator.add_parameter(IntegerParameter("ndiv", 2, 2))
        manipulator.add_parameter(IntegerParameter("rfact", 0, 4))
        manipulator.add_parameter(IntegerParameter("bcast", 0, 5))
        manipulator.add_parameter(IntegerParameter("depth", 0, 4))
        manipulator.add_parameter(IntegerParameter("swap", 0, 2))
        manipulator.add_parameter(IntegerParameter("swapping_threshold", 64, 128))
        manipulator.add_parameter(IntegerParameter("L1_transposed", 0, 1))
        manipulator.add_parameter(IntegerParameter("U_transposed", 0, 1))
        manipulator.add_parameter(IntegerParameter("mem_alignment", 4, 16))
        
        return manipulator
        
    def output_hpl_datfile(self, params):
        """HPL uses an input file to express the parameters, and this uses mako to render it."""
        params["size"] = self.args.size
        from mako.template import Template
        template = Template(filename="HPL.dat.mako")
        with open("HPL.dat", "w") as f:
            f.write(template.render(**params))
            
    def get_time_from_hpl_output(self, fname="HPL.out"):
        """Returns the elapsed time only, from the HPL output file"""
        #FIXME: clean up with REs
        elapsed = 0.0
        with open(fname) as f:
            line = f.readline()
            while (line[0:3] != "T/V"):
                line = f.readline()
            line = f.readline()
            while (line[0:3] != "T/V"):
                line = f.readline()
            f.readline() # line of dashes
            splitted = f.readline().split()
            elapsed = float(splitted[5])
        
        return elapsed
                    
    
    def program_name(self):
        return "HPL"
    
    def program_version(self):
      return "size=%d,nprocs=%d" % (self.args.size, self.args.nprocs)

    def save_final_config(self, configuration):
      '''
      called at the end of autotuning with the best resultsdb.models.Configuration
      '''
      print "Final configuration", configuration.data
            
if __name__ == '__main__':
  args = parser.parse_args()
  HPLinpack.main(args)