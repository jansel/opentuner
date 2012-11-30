#!/usr/bin/python
import abc 
import itertools
import logging 
import math 
import os
import random
import subprocess
import sys
import tempfile
from pprint import pprint
from collections import defaultdict


class ConfigurationManipulator(object):
  __metaclass__ = abc.ABCMeta
  
  @abc.abstractmethod
  def random(self):
    '''produce a random initial configuration'''
    return

  @abc.abstractmethod
  def cartesian_veiw(self, config):
    '''return a list of CartesianParameter objects'''
    return

  @abc.abstractmethod
  def maze_veiw(self, config):
    '''return a list of MazeParameter objects'''
    return

  def validate(self, config):
    '''is the given config valid???'''
    return all(map(lambda x: x.validate(config),
                   self.cartesian_veiw()+self.maze_veiw()))


class Parameter(object):
  __metaclass__ = abc.ABCMeta

  def __init__(self, name):
    self.name = name

  def validate(self, config):
    '''is the given config valid???'''
    return True

class CartesianParameter(Parameter):
  @abc.abstractmethod
  def set(self, config, value):
    '''assign this value in the given configuration'''
    pass

  @abc.abstractmethod
  def get(self, config):
    '''retrieve this value from the given configuration'''
    return 0

  @abc.abstractmethod
  def range(self):
    '''return the legal range for this parameter, inclusive'''
    return (0, 1)

  @property
  def type(self):
    return int

  
class MazeParameter(Parameter):
  @abc.abstractmethod
  def possible_directions(self, config):
    '''number legal directions that can be taken from the current position'''
    return 1

  @abc.abstractmethod
  def step(self, config, direction, magnitute=1.0):
    '''change the given configuration by taking a step in the given direction'''
    pass

  @abc.abstractmethod
  def randomize(self, config):
    '''randomize this value without taking into account the current position'''
    pass


def rnd_uniform(min, max):
  return int(random.uniform(min,
                            max+1))

def rnd_loguniform(min, max):
  r = 1-math.log(random.uniform(1, 10*4))/math.log(10*4)
  return int((max-min)*r+min)

def rnd_lognormal(mean, minv, maxv):
  if maxv-minv < 16:
    return rnd_uniform(minv, maxv)
  r = None
  while r is None:
    try:
      r = math.log(random.normalvariate(2, 4), 2)
      if r<0:
        r=None
    except ValueError:
      pass
  r = int(r*(mean-minv)+minv)
  return max(minv, min(r, maxv))

def rnd_normal(mean, minv, maxv):
  if maxv-minv < 16:
    return rnd_uniform(minv, maxv)
  r = None
  while r is None:
    try:
      r = random.normalvariate(1,0.5)
      if r<0:
        r=None
    except ValueError:
      pass
  r = int(r*(mean-minv)+minv)
  return max(minv, min(r, maxv))







def hillclimb(p1, p2, minv, maxv):
  delta = p2-p1
  v = p2+delta
  if minv is not None and v < minv:
    return minv
  if maxv is not None and v > maxv:
    return maxv
  return v

class Item(object):
  def __init__(self, info, name, min=None, max=None, type='algchoice'):
    if min is not None:
      min = int(min)
    if max is not None:
      max = int(max)
    self._info = info
    self._name = name
    self._min  = min 
    self._max  = max 
    self._type = type 

  def __str__(self, rest="..."):
    return "%s(info, '%s', %s)" % (self.__class__.__name__, self._name, rest)

  __repr__=__str__

  @property
  def name(self):
    return self._name
  
  def tunables(self):
    return (self._name,)

  def randomize(self, cfg, n):
    logging.error("randomize must be implemented "+self.__class__.__name__)

  def mutate(self, cfg, n):
    self.randomize(cfg, n)

  def mutateChance(self, chance, cfg, n):
    if random.random()<chance:
      self.mutate(cfg, n)

  def copyValues(self, src, dst):
    if src is dst:
      return
    for t in self.tunables():
      dst[t] = src[t]

  def hillclimb(self, p1, p2, output, n):
    for t in self.tunables():
      output[t] = hillclimb(p1[t], p2[t], self._min, self._max)

class Selector(Item):
  max_levels = 13
  disabled = 2**31

  def __init__(self, info, name, rules):
    self.rulecount = int(rules)
    Item.__init__(self, info, name)

  def randomize(self, cfg, n):
    levels = 2
    while random.choice((True, False)):
      levels += 1
    levels = min(levels, Selector.max_levels)
    cfg[self.tunable_rule(1)] = self.randomrule()
    v = 0
    for i in xrange(2, levels):
      v += rnd_loguniform(v, n)
      cfg[self.tunable_cutoff(i)] = v
      cfg[self.tunable_rule(i)] = self.randomrule()
    for i in xrange(levels, Selector.max_levels):
      cfg[self.tunable_cutoff(i)] = Selector.disabled
      cfg[self.tunable_rule(i)] = 0

  def mutateChance(self, chance, cfg, n):
    roll = lambda: random.random()<chance
    for i in xrange(2, Selector.max_levels):
      if i==2:
        low = 1
      else:
        low = cfg[self.tunable_cutoff(i-1)]
      if i==Selector.max_levels-1:
        high = n
      else:
        high = min(n, cfg[self.tunable_cutoff(i+1)])
      if cfg[self.tunable_cutoff(i)] >= Selector.disabled:
        if roll():
          cfg[self.tunable_cutoff(i)] = rnd_loguniform(low, high)
          cfg[self.tunable_rule(i)] = self.randomrule()
        return
      else: 
        if roll():
          cfg[self.tunable_cutoff(i)] = rnd_lognormal(cfg[self.tunable_cutoff(i)], low, high)

  def hillclimb(self, p1, p2, output, n):
    for i in xrange(2, Selector.max_levels):
      if i==2:
        low = 0
      else:
        low = output[self.tunable_cutoff(i-1)]
      if i==Selector.max_levels-1:
        high = n
      else:
        high = min(n, output[self.tunable_cutoff(i+1)])
      if p1[self.tunable_cutoff(i)] >= Selector.disabled \
          and p2[self.tunable_cutoff(i)] >= Selector.disabled:
        output[self.tunable_cutoff(i)] = hillclimb(p1[self.tunable_cutoff(i)], p2[self.tunable_cutoff(i)], low, high)

  def randomrule(self):
    return random.choice(range(self.rulecount))

  def tunables(self):
    return map(self.tunable_rule,   xrange(1,Selector.max_levels)) \
          +map(self.tunable_cutoff, xrange(2,Selector.max_levels))
  
  def tunable_rule(self, i):
    return self.name+"_lvl"+str(i)+"_rule"  

  def tunable_cutoff(self, i):
    return self.name+"_lvl"+str(i)+"_cutoff"
        

class SynthesizedFunction(Item):
  def tunables(self):
    return [self.name+"__"+str(i) for i in xrange(32)]

  def randomize(self, cfg, n):
    v = rnd_loguniform(self._min, self._max)
    b = float(2**32)
    for i,k in enumerate(self.tunables()):
      cfg[k] = int(v/b*float(2**i))


class Tunable(Item):
  pass

class Cutoff(Tunable):
  def randomize(self, cfg, n):
    cfg[self.name] = rnd_loguniform(self._min, min(n,self._max))

  def mutate(self, cfg, n):
    cfg[self.name] = rnd_lognormal(cfg[self.name], self._min, min(n,self._max))

class Switch(Tunable):
  def randomize(self, cfg, n):
    cfg[self.name] = rnd_uniform(self._min, self._max)

  def hillclimb(self, p1, p2, output, n):
    pass
  
class Ignore(Item):
  def randomize(self, cfg, n):
    pass

configctor = {'algchoice.alg'                 : None,#handled in selector creation cod
              'algchoice.cutoff'              : None,#handled in selector creation cod
              'system.cutoff.distributed'     : Cutoff,
              'system.cutoff.sequential'      : Cutoff,
              'system.cutoff.splitsize'       : Cutoff,
              'system.data.distribution.size' : Cutoff,
              'system.data.distribution.type' : Switch,
              'system.data.migration.type'    : Switch,
              'system.flag.unrollschedule'    : Switch,
              'system.runtime.threads'        : Ignore,
              'system.tunable.accuracy.array' : SynthesizedFunction,
              'user.tunable.accuracy.array'   : SynthesizedFunction,
              'user.tunable.array'            : SynthesizedFunction,
              'user.tunable'                  : Cutoff,
  }


class HighLevelConfig(object):
  def __init__(self, info):
    tunables = info.tunablesDict()
    self.items=list()

    for ac in info.algchoices():
      self.items.append(Selector(info, ac['name'], ac['rules']))

    for t in tunables.values():
      if t['type'] not in configctor.keys():
        logging.error("tunable type %s unknown" % t['type'])
        continue
      if configctor[t['type']] is not None:
        self.items.append(configctor[t['type']](info=info,
                                                name=t['name'],
                                                min=t['min'],
                                                max=t['max'],
                                                type=t['type']))
    self.items.sort(key=lambda x: x.name)

  def randomize(self, cfg, n):
    for item in self.items:
      item.randomize(cfg, n)

  def mutateChance(self, chance, cfg, n):
    for item in self.items:
      item.mutateChance(chance, cfg, n)

  def crossover(self, src1, src2, dst):
    p1=rnd_uniform(0, len(self.items))
    p2=rnd_uniform(0, len(self.items))
    if p1>p2:
      p1,p2 = p2,p1
    for i,item in enumerate(self.items):
      if p1 <= i and i < p2:
        item.copyValues(src2, dst)
      else:
        item.copyValues(src1, dst)

  def hillclimb(self, p1, p2, output, n):
    for item in self.items:
      item.hillclimb(p1, p2, output, n)


def test_randoms(mean=150, low=100, high=300, trials = 100000):
  randoms = {
      'rnd_uniform'    : lambda: rnd_uniform    (low, high),
      'rnd_loguniform' : lambda: rnd_loguniform (low, high),
      'rnd_lognormal'  : lambda: rnd_lognormal  (mean, low, high) ,
      'rnd_normal'     : lambda: rnd_normal  (mean, low, high) ,
      }
  names = randoms.keys()
  stats = dict([(name, [0]*(1-low+high)) for name in names])
  for name, fn in randoms.iteritems():
    for t in xrange(trials):
      v = fn()
      if v<low:
        logging.warning(name+" produced a value too low "+str(v))
        continue
      if v>high:
        logging.warning(name+" produced a value too low "+str(v))
        continue
      v=fn()
      if v<low:
        print "error",name,"returned",v
      stats[name][v-low] += 1

  datafile = open('test_randoms.dat', 'w')
  print >>datafile, "#val ", ' '.join(names)
  for v in xrange(low, high):
    print >>datafile, v, ' '.join(["%03.5f"%(100.0*stats[name][v-low]/float(trials)) for name in names])
  datafile.close()
  print 'wrote test_randoms.dat'
  plotfile = open('test_randoms.gnuplot', 'w')
  print >>plotfile, '''
set terminal postscript eps enhanced color
set xlabel "Value"
set ylabel "Percent"
set size .75,.75
#set yrange [0:2]
  '''
  print >>plotfile, 'plot',
  for i,name in enumerate(names):
    if i==0:
      print >>plotfile, "'test_randoms.dat'",
    else:
      print >>plotfile, ", ''",
    print >>plotfile, '''using 1:%d title "%s" w l lw 3''' % (2+i, name.replace('_',' ')),
  print >>plotfile 
  plotfile.close()
  print 'wrote test_randoms.gnuplot'
  subprocess.check_call(['gnuplot'], stdin=open('test_randoms.gnuplot'), stdout=open('test_randoms.pdf','w'))
  print 'wrote test_randoms.pdf'



if __name__ == '__main__':
  test_randoms()

