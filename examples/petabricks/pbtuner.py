#!/usr/bin/python
import deps #fix sys.path
import re
from pprint import pprint
from opentuner.search.manipulator import (ConfigurationManipulator,
                                         IntegerParameter,
                                         FloatParameter)

cfg=open('linux_static_x86_64/Sort2.cfg.default').read()

manipulator = ConfigurationManipulator()

for m in re.finditer(r" *([a-zA-Z0-9_-]+)[ =]+([0-9e.+-]+) *[#] *([a-z]+).* ([0-9]+) to ([0-9]+)", cfg):
  k, v, valtype, minval, maxval =  m.group(1,2,3,4,5)
  assert valtype=='int'
  manipulator.add_cartesian_parameter(IntegerParameter(k, minval, maxval))

pprint(manipulator.random())
