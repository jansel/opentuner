#!/usr/bin/env python
#
# This is a simple testcase purely for testing the autotuner on permutations
#
# http://en.wikipedia.org/wiki/Travelling_salesman_problem
#

import adddeps #fix sys.path

import argparse
import logging

import opentuner
from opentuner.search.manipulator import (ConfigurationManipulator,
                                          PermutationParameter)
from opentuner.search.objective import MinimizeTime
from opentuner.measurement import MeasurementInterface
from opentuner.measurement.inputmanager import FixedInputManager
from opentuner.tuningrunmain import TuningRunMain


parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('data', help='distance matrix file')

class TSP(MeasurementInterface):
    def __init__(self, args):
        super(TSP, self).__init__(args)
        data = args.data
        m = open(data).readlines()
        self.distance = [[int(i) for i in l.split()] for l in m]

    def run(self, desired_result, input, limit):
        cfg = desired_result.configuration.data
        p = cfg[0]      # cheating: should use manipulator function
        t = self.eval_path(p)
        return opentuner.resultsdb.models.Result(time=t)

    def eval_path(self, p):
        """ Given permutation of cities as a list of indices,
        return total path length """
        out = sum(self.distance[p[i]][p[i+1]] for i in range(len(p)-1))
##        print out, p
        return out

    def manipulator(self):
        manipulator = ConfigurationManipulator()
        manipulator.add_parameter(PermutationParameter(0, range(len(self.distance))))
        return manipulator

    def solution(self):
        p = [1,13,2,15,9,5,7,3,12,14,10,8,6,4,11]
        return self.eval_path(p)



if __name__ == '__main__':
  args = parser.parse_args()
  TSP.main(args)

