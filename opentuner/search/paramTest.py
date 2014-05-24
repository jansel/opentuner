# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab autoindent smarttab
from manipulator import *
import random 

# IntegerParameter

def testIntegerSwarm():
  name = 'int1'
  pmin = -10 
  pmax = 10
  # vals = [random.randint(1, 100) for i in range(pmin, pmax+1)]
  p = IntegerParameter(name, pmin, pmax)
  v = -10
  pos = {name:0}
  gb = {name:4}
  lb = {name:9}
  p.swarm_sv(pos, gb, lb, 0.5, 0.3, 0.3, v)


def testBooleanSwarm():
  name = 'bool1'
  p = BooleanParameter(name)
  v = 2  
  pos = {name:0}
  gb = {name:1}
  lb = {name:0}
  p.swarm_sv(pos, gb, lb, 0.5, 0.3, 0.3, v)

testIntegerSwarm()
testBooleanSwarm()
