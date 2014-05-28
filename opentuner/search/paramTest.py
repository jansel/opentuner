# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab autoindent smarttab
from manipulator import *
import random 

# swarm_sv

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
  v = 0 
  pos = {name:0}
  gb = {name:1}
  lb = {name:0}
  p.swarm_sv(pos, gb, lb, 0.5, 0.3, 0.3, v)

def testPermSwarm():
  name = 'perm1'
  p = PermutationParameter(name)
  pos = {name: [3,1,4,2,5]}
  gb = {name: [3,1,2,4,5]}
  lb = {name: [1,3,2,4,5]}
  p.swarm_sv(pos, gb, lb, 0.5, 0.3, 0.3)
  pass

def testArraySwarm():
  pass

# Crossover
def testPermCross():
  pass

def testArrayCross():
  pass

# dif_sv
def testArrayDiff():
  pass

def testPermDiff():
  pass

# mutate


testPermSwarm()
