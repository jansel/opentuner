#!/usr/bin/python
import abc
import collections
import copy
import hashlib
import itertools
import logging
import math
import os
import random
import subprocess
import sys
import tempfile

from fn import _
from pprint import pprint
from collections import defaultdict

log = logging.getLogger(__name__)

class ConfigurationManipulatorBase(object):
  '''
  abstract interface for objects used by search techniques to mutate
  configurations
  '''
  __metaclass__ = abc.ABCMeta

  def validate(self, config):
    '''is the given config valid???'''
    return all(map(_.validate(config), self.parameters()))

  def normalize(self, config):
    '''mutate config into canonical form'''
    for param in self.parameters(config):
      param.normalize(config)

  def set_search_driver(self, search_driver):
    '''called exactly once during setup'''
    pass

  def copy(self, config):
    '''produce copy of config'''
    return copy.deepcopy(config)

  def parameters_dict(self, config):
    '''convert self.parameters() to a dictionary by name'''
    return dict([(p.name, p) for p in self.parameters(config)])

  def param_names(self, *args):
    '''return union of parameter names in args'''
    return sorted(reduce(set.union,
                  [set(map(_.name, self.parameters(cfg)))
                   for cfg in args]))

  def linear_config(self, a, cfg_a, b, cfg_b, c, cfg_c):
    '''return a configuration that is a linear combination of 3 other configs'''
    dst = self.copy(cfg_a)
    dst_params = self.proxy(dst)
    for k in self.param_names(dst, cfg_a, cfg_b, cfg_c):
      dst_params[k].set_linear(a, cfg_a, b, cfg_b, c, cfg_c)
    return dst

  def proxy(self, cfg):
    return ManipulatorProxy(self, cfg)

  @abc.abstractmethod
  def random(self):
    '''produce a random initial configuration'''
    return

  @abc.abstractmethod
  def parameters(self, config):
    '''return a list of of Parameter objects'''
    return

  @abc.abstractmethod
  def hash_config(self, config):
    '''produce unique hash value for the given config'''
    return

class ConfigurationManipulator(ConfigurationManipulatorBase):
  '''
  a configuration manipulator using a fixed set of parameters and storing
  configs in a dict-like object
  '''

  def __init__(self, params=[], config_type=dict, seed_config=None, **kwargs):
    self.params = list(params)
    self.config_type = config_type
    self.search_driver = None
    self._seed_config = seed_config
    super(ConfigurationManipulator, self).__init__(**kwargs)
    for p in self.params:
      p.parent=self

  def add_parameter(self, p):
    p.set_parent(self)
    self.params.append(p)

    sub_params = p.sub_parameters()
    for sp in sub_params:
      sp.set_parent(p)
    self.params.extend(sub_params)

  def set_search_driver(self, search_driver):
    self.search_driver = search_driver

  def seed_config(self):
    '''produce a fixed seed configuration'''
    if self._seed_config:
      cfg = copy.deepcopy(self._seed_config)
    else:
      cfg = self.config_type()
      for p in self.params:
        if not isinstance(p.name, str) or '/' not in p.name:
          cfg[p.name] = p.seed_value()
    return cfg

  def random(self):
    '''produce a random configuration'''
    cfg = self.seed_config()
    for p in self.parameters(cfg):
      p.randomize(cfg)
    return cfg

  def parameters(self, config):
    '''return a list of Parameter objects'''
    if type(config) is not self.config_type:
      log.error("wrong type, expected %s got %s",
                str(self.config_type),
                str(type(config)))
      raise TypeError()
    return self.params


  def hash_config(self, config):
    '''produce unique hash value for the given config'''
    m = hashlib.sha256()
    params = list(self.parameters(config))
    params.sort(key=_.name)
    for i, p in enumerate(params):
      m.update(str(p.name))
      m.update(p.hash_value(config))
      m.update(str(i))
      m.update("|")
    return m.hexdigest()


  def search_space_size(self):
    '''estimate the size of the search space, not precise'''
    return reduce(_ * _, [x.search_space_size() for x in self.params])

#####

class Parameter(object):
  '''
  abstract base class for parameters in a ConfigurationManipulator
  '''
  __metaclass__ = abc.ABCMeta

  def __init__(self, name):
    self.name = name
    self.parent = None
    super(Parameter, self).__init__()

  def _to_storage_type(self, val):
    '''hook to support transformation applied while stored'''
    return val

  def _from_storage_type(self, sval):
    '''hook to support transformation applied while stored'''
    return sval

  def _read_node(self, config):
    '''hook to support different storage structures'''
    node = config
    if not isinstance(self.name, str):
      return node, self.name
    name_parts = self.name.split('/')
    for part in name_parts[:-1]:
      if isinstance(node, list):
        part = int(part)
      node = node[part]
    part = name_parts[-1]
    if isinstance(node, list):
      part = int(part)
    return node, part


  def _get(self, config):
    '''hook to support different storage structures'''
    node, part = self._read_node(config)
    return self._from_storage_type(node[part])

  def _set(self, config, v):
    '''hook to support different storage structures'''
    node, part = self._read_node(config)
    node[part] = self._to_storage_type(v)

  def set_parent(self, manipulator):
    self.parent = manipulator

  def validate(self, config):
    '''is the given config valid???'''
    return True

  def is_primitive(self, ignored = None):
    return isinstance(self, PrimitiveParameter)

  def is_permutation(self, ignored=None):
    return isinstance(self, PermutationParameter)

  def manipulators(self, config):
    '''
    a list of manipulator functions to change this value in the config
    manipulators must be functions that take a config and change it in place

    default implementation just has randomize as only operation
    '''
    return [self.randomize]

  def normalize(self, config):
    '''
    mutate this parameter into a canonical form
    '''
    pass


  def sub_parameters(self):
    '''
    additional parameters added with this parameter
    '''
    return []

  @abc.abstractmethod
  def randomize(self, config):
    '''randomize this value without taking into account the current position'''
    pass

  @abc.abstractmethod
  def seed_value(self):
    '''some legal value of this parameter (for creating initial configs)'''
    return

  @abc.abstractmethod
  def copy_value(self, src, dst):
    '''copy the value of this parameter from src to dst config'''
    pass

  @abc.abstractmethod
  def same_value(self, cfg1, cfg2):
    '''test if cfg1 and cfg2 have the same value of this parameter'''
    return

  @abc.abstractmethod
  def hash_value(self, config):
    '''produce unique hash for this value in the config'''
    return

  @abc.abstractmethod
  def set_linear(self, cfg_dst, a, cfg_a, b, cfg_b, c, cfg_c):
    '''set this value to a*cfg_a + b*cfg_b, + c*cfg_c'''
    pass

  def search_space_size(self):
    return 1

class PrimitiveParameter(Parameter):
  '''
  a single dimension in a cartesian space, with a minimum and a maximum value
  '''
  __metaclass__ = abc.ABCMeta

  def __init__(self, name, value_type=float, **kwargs):
    self.value_type = value_type
    super(PrimitiveParameter, self).__init__(name, **kwargs)

  def hash_value(self, config):
    '''produce unique hash for this value in the config'''
    self.normalize(config)
    return hashlib.sha256(repr(self.get_value(config))).hexdigest()

  def copy_value(self, src, dst):
    '''copy the value of this parameter from src to dst config'''
    self.set_value(dst, self.get_value(src))

  def same_value(self, cfg1, cfg2):
    '''test if cfg1 and cfg2 have the same value of this parameter'''
    return self.get_value(cfg1) == self.get_value(cfg2)

  def is_integer_type(self):
    '''true if self.value_type can only represent integers'''
    return self.value_type(0) == self.value_type(0.1)

  def get_unit_value(self, config):
    '''get_value scaled such that range is between 0.0 and 1.0'''
    low, high = self.legal_range(config)
    if self.is_integer_type():
      # account for rounding
      low -= 0.4999
      high += 0.4999
    val = self.get_value(config)
    if low < high:
      return float(val-low)/float(high-low)
    else:
      if low > high:
        log.warning('invalid range for parameter %s, %s to %s',
                    self.name, low, high)
      # only a single legal value!
      return 0.0

  def set_unit_value(self, config, unit_value):
    '''set_value scaled such that range is between 0.0 and 1.0'''
    assert 0.0 <= unit_value and unit_value <= 1.0
    low, high = self.legal_range(config)
    if self.is_integer_type():
      # account for rounding
      low -= 0.4999
      high += 0.4999
    if low < high:
      val = unit_value*float(high-low) + low
      if self.is_integer_type():
        val = round(val)
      val = max(low, min(val, high))
      self.set_value(config, self.value_type(val))

  def set_linear(self, cfg_dst, a, cfg_a, b, cfg_b, c, cfg_c):
    '''set this value to a*cfg_a + b*cfg_b, + c*cfg_c'''
    va = self.get_unit_value(cfg_a)
    vb = self.get_unit_value(cfg_b)
    vc = self.get_unit_value(cfg_c)
    v = a*va + b*vb + c*vc
    v = max(0.0, min(v, 1.0))

    self.set_unit_value(cfg_dst, v)

  def normal_mutation(self, cfg, sigma = 0.1):
    '''
    apply normally distributed noise to the value of this parameter in cfg

    sigma is the stddev of the normal distribution on a unit scale (search
    space is of size 1)
    '''
    v = self.get_unit_value(cfg)
    v += random.normalvariate(0.0, sigma)
    # handle boundary cases by reflecting off the edge
    if v < 0.0:
      v *= -1.0
    if v > 1.0:
      v = 1.0 - (v % 1)
    self.set_unit_value(cfg, v)

  def manipulators(self, config):
    '''
    a list of manipulator functions to change this value in the config
    manipulators must be functions that take a config and change it in place

    for primitive params default implementation is uniform random and normal
    '''
    return [self.randomize, self.normal_mutation]

  @abc.abstractmethod
  def set_value(self, config, value):
    '''assign this value in the given configuration'''
    pass

  @abc.abstractmethod
  def get_value(self, config):
    '''retrieve this value from the given configuration'''
    return 0

  @abc.abstractmethod
  def legal_range(self, config):
    '''return the legal range for this parameter, inclusive'''
    return (0, 1)

class NumericParameter(PrimitiveParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    '''min/max are inclusive'''
    assert min_value <= max_value
    super(NumericParameter, self).__init__(name, **kwargs)
    #after super call so self.value_type is initialized
    self.min_value = self.value_type(min_value)
    self.max_value = self.value_type(max_value)

  def seed_value(self):
    '''some legal value of this parameter (for creating initial configs)'''
    return self.min_value

  def set_value(self, config, value):
    assert value >= self.min_value
    assert value <= self.max_value
    self._set(config, value)

  def get_value(self, config):
    return self._get(config)

  def legal_range(self, config):
    return (self.min_value, self.max_value)

  def difference(self, cfg, cfg1, cfg2):
    v = self.get_value(cfg2)-self.get_value(cfg1)
    v = max(self.min_value, min( self.max_value, v))
    self.set_value(cfg, v)

  def scale(self, cfg, k):
    v = self.get_value(cfg)*k
    v = max(self.min_value, min( self.max_value, v))
    self.set_value(cfg, v)

  def sum(self, cfg, *cfgs):
    v = sum([self.get_value(c) for c in cfgs])
    v = max(self.min_value, min( self.max_value, v))
    self.set_value(cfg, v)    
    
    
  def randomize(self, config):
    if self.is_integer_type():
      self.set_value(config, random.randint(*self.legal_range(config)))
    else:
      self.set_value(config, random.uniform(*self.legal_range(config)))

  def search_space_size(self):
    if self.value_type is float:
      return 2**32
    else:
      return self.max_value - self.min_value

class IntegerParameter(NumericParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    '''min/max are inclusive'''
    kwargs['value_type'] = int
    super(IntegerParameter, self).__init__(name, min_value, max_value, **kwargs)

class FloatParameter(NumericParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    '''min/max are inclusive'''
    kwargs['value_type']=float
    super(FloatParameter, self).__init__(name, min_value, max_value, **kwargs)

class ScaledNumericParameter(NumericParameter):
  @abc.abstractmethod
  def _scale(self, v):
    return v

  @abc.abstractmethod
  def _unscale(self, v):
    return v

  def set_value(self, config, value):
    NumericParameter.set_value(self, config, self._unscale(value))

  def get_value(self, config):
    return self._scale(NumericParameter.get_value(self, config))

  def legal_range(self, config):
    return map(self._scale, NumericParameter.legal_range(self, config))

class LogIntegerParameter(ScaledNumericParameter):
  '''
  a numeric parameter that is searched on a log scale, but stored without
  scaling
  '''
  def _scale(self, v):
    return math.log(v + 1.0 - self.min_value, 2.0)

  def _unscale(self, v):
    v = 2.0**v - 1.0 + self.min_value
    v = int(round(v))
    return v

  def legal_range(self, config):
    low, high = NumericParameter.legal_range(self, config)
    # increase the bounds account for rounding
    return  self._scale(low - 0.4999), self._scale(high + 0.4999)

class LogFloatParameter(ScaledNumericParameter):
  '''
  a numeric parameter that is searched on a log scale, but stored without
  scaling
  '''
  def _scale(self, v):
    return math.log(v + 1.0 - self.min_value, 2.0)

  def _unscale(self, v):
    v = 2.0**v - 1.0 + self.min_value
    return v

class PowerOfTwoParameter(ScaledNumericParameter):
  '''An integer power of two, with a given min and max value'''
  def __init__(self, name, min_value, max_value, **kwargs):
    kwargs['value_type'] = int
    assert min_value >= 1
    assert math.log(min_value, 2) % 1 == 0  # must be power of 2
    assert math.log(max_value, 2) % 1 == 0  # must be power of 2
    super(PowerOfTwoParameter, self).__init__(name, min_value, max_value,
                                              **kwargs)
  def _scale(self, v):
    return int(math.log(v, 2))

  def _unscale(self, v):
    return 2**int(v)

  def legal_range(self, config):
    return int(math.log(self.min_value, 2)), int(math.log(self.max_value, 2))

##################

class ComplexParameter(Parameter):
  '''
  a non-cartesian parameter that can't be manipulated directly, but has a set
  of user defined manipulation functions
  '''

  def copy_value(self, src, dst):
    '''copy the value of this parameter from src to dst config'''
    self._set(dst, copy.deepcopy(self._get(src)))

  def same_value(self, cfg1, cfg2):
    '''test if cfg1 and cfg2 have the same value of this parameter'''
    return self._get(cfg1) == self._get(cfg2)

  def hash_value(self, config):
    '''produce unique hash for this value in the config'''
    self.normalize(config)
    return hashlib.sha256(repr(self._get(config))).hexdigest()

  def set_linear(self, cfg_dst, a, cfg_a, b, cfg_b, c, cfg_c):
    '''
    set this value to a*cfg_a + b*cfg_b + c*cfg_c

    this operation is not possible in general with complex parameters but
    we make an attempt to "fake" it for common use cases
    '''
    # attempt to normalize order, we prefer a==1.0
    if a != 1.0 and b == 1.0: # swap a and b
      a, cfg_a, b, cfg_b = b, cfg_b, a, cfg_a
    if a != 1.0 and c == 1.0: # swap a and c
      a, cfg_a, c, cfg_c = c, cfg_c, a, cfg_a

    # attempt to normalize order, we prefer b==-c
    if b < c: # swap b and c
      b, cfg_b, c, cfg_c = c, cfg_c, b, cfg_b
    if b != -c and a == -c: # swap a and c
      a, cfg_a, c, cfg_c = c, cfg_c, a, cfg_a

    if a == 1.0 and b == -c:
      self.copy_value(cfg_a, cfg_dst)
      self.add_difference(cfg_dst, b, cfg_b, cfg_c)
    else:
      # TODO: should handle more cases
      self.randomize()

  def add_difference(self, cfg_dst, scale, cfg_b, cfg_c):
    '''
    add the difference cfg_b-cfg_c to cfg_dst

    this is the key operation used in differential evolution
    and some simplex techniques

    this operation is not possible in general with complex parameters but
    we make an attempt to "fake" it
    '''
    if not self.same_value(cfg_b, cfg_c):
      self.randomize(cfg_dst)

  @abc.abstractmethod
  def randomize(self, config):
    '''randomize this value without taking into account the current position'''
    pass

  @abc.abstractmethod
  def seed_value(self):
    '''some legal value of this parameter (for creating initial configs)'''
    return


class BooleanParameter(ComplexParameter):
  def manipulators(self, config):
    return [self.flip]

  def randomize(self, config):
    self._set(config, self.seed_value())

  def seed_value(self):
    return random.choice((True, False))

  def flip(self, config):
    self._set(config, not self._get(config))

  def search_space_size(self):
    return 2


class SwitchParameter(ComplexParameter):
  '''
  a switch parameter is an unordered collection of options with no implied
  correlation between the choices, choices are range(option_count)
  '''
  def __init__(self, name, option_count):
    self.option_count = option_count
    super(SwitchParameter, self).__init__(name)

  def randomize(self, config):
    self._set(config, random.randrange(self.option_count))

  def seed_value(self):
    return random.randrange(self.option_count)

  def search_space_size(self):
    return max(1, self.option_count)


class EnumParameter(ComplexParameter):
  '''
  same as a SwitchParameter but choices are taken from an arbitrarily typed list
  '''
  def __init__(self, name, options):
    super(EnumParameter, self).__init__(name)
    self.options = list(options)

  def randomize(self, config):
    self._set(config, random.choice(self.options))

  def seed_value(self):
    return random.choice(self.options)

  def search_space_size(self):
    return max(1, len(self.options))


class PermutationParameter(ComplexParameter):
  def __init__(self, name, items):
    super(PermutationParameter, self).__init__(name)
    self._items = list(items)

  def randomize(self, config):
    random.shuffle(self._get(config))
    self.normalize(config)

  def small_random_change(self, config):
    cfg_item = self._get(config)
    for i in xrange(1, len(cfg_item)):
      if random.random() < 0.25:
        # swap
        cfg_item[i-1], cfg_item[i] = cfg_item[i], cfg_item[i-1]
    self.normalize(config)

  def seed_value(self):
    return list(self._items) # copy

  def manipulators(self, config):
    return [self.randomize, self.small_random_change]
  
  def get_value(self, config):
    return self._get(config)

# Swap-based operator
  def swap_dist(self, cfg1, cfg2):
    '''
    Return list of swaps needed to transform the permutation from cfg1 to cfg2. A swap is represented by a tuple of indices (a,b)
    which swaps items at position a and b in the permutation. See "Particle swarm optimization for traveling salesman problem"
    http://ieeexplore.ieee.org/xpls/abs_all.jsp?arnumber=1259748
    '''
    p1 = self.get_value(cfg1)[:]
    p2 = self.get_value(cfg2)[:]
    assert len(p1)==len(p2)
    swaps = []
    for i in range(len(p1)):
        if p1[i]!=p2[i]:
            j=p1.index(p2[i])
            swaps.append( (i,j))
            v = p1[i]
            p1[i]=p1[j]
            p1[j]=v

    return swaps

  def scale_swaps(self, swaps, k):
    """ Multiply operation in PSO """
    if k>=0:
      if k<1:
        return swaps[:int(k*len(swaps))]
      else:
        return swaps*int(k)+swaps[:int((k%1)*len(swaps))]
    else:      
      return self.scale_swaps(list(reversed(swaps)), -k)
    return new
    
  def sum_swaps(self, *swaps):
    return reduce(lambda x,y: x+y, swaps)

  def split_swaps(self, swaps, k):
    """
    Splits a swap sequence using a ratio k, a float in the range [0,1]
    Return two subsequences
    """
    s = int(k*len(swaps))
    return swaps[:s], swaps[s:]
    
    
  def apply_swaps(self, swaps, cfg):
    """ Return a new cfg by applying a sequence of swaps to given cfg """
    p = self.get_value(cfg)
    for s in swaps:
      i,j=s
      v = p[i]
      p[i]=p[j]
      p[j]=v

  

  # Mutation operators
  def random_swap(self, cfg, d=5):
    """
    Swap a random pair of items seperated by distance d
    """
    new = self.parent.copy(cfg)
    p = self.get_value(new)
    r = random.randint(0,len(p)-d-1)
    self.apply_swaps([(r, r+d)],new)
    return new

  def random_invert(self, cfg, d=5):
    """
    Randomly invert a length-d subsection of the permutation
    """
    new = self.parent.copy(cfg)
    p = self.get_value(new)
    r = random.randint(0,len(p)-d)
    subpath = p[r:r+d][:]
    subpath.reverse()
    p[r:r+d]=subpath
    return new

    

  # Crossover operators
  def PX(self, cfg1, cfg2, c1=None, c2=None):
    """
    Partition crossover (Whitley 2009?)
    Change the order of items up to c1 in cfg1 according to their order in cfg2.
    """

    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    if not c1:
      c1 = random.randint(0,len(p1))
##    if not c2:
##      c2 = random.randint(0,len(p2))

    new1 = self.parent.copy(cfg1)
##    new2 = self.parent.copy(cfg2)

    new1[self.name] = sorted(p1[:c1], key=lambda x: p2.index(x))+p1[c1:]
##    new2[self.name] = sorted(p2[:c2], key=lambda x: p1.index(x))+p2[c2:]
    return new1, None

  def PMX(self, cfg1, cfg2, d=5):
    """
    Partially-mapped crossover Goldberg & Lingle (1985)
    """
    new1 = self.parent.copy(cfg1)
    new2 = self.parent.copy(cfg2)
    
    p1 = self.get_value(new1)
    p2 = self.get_value(new2)
    
    r = random.randint(0,len(p1)-d)
    c1 = p1[r:r+d]
    c2 = p2[r:r+d]

    # Construct partial map
    pm = dict([ (c1[i], c2[i]) for i in range(d)])
    agenda = c1[:]
    while agenda!=[]:
      n = agenda.pop()
      while pm[n] in pm:
        if n == pm[n]:
          pm.pop(n)
          break
        try:
            agenda.remove(pm[n])
        except:
          pass
        link = pm.pop(pm[n])
        pm[n] = link
    # Reversed partial map    
    pm2 = {v:k for k,v in pm.items()}
    # Fix conflicts
    for k in pm:
      p2[p2.index(k)]=pm[k]
    for k in pm2:
      p1[p1.index(k)]=pm2[k]        
    # Cross over
    p1[r:r+d] = c2     
    p2[r:r+d] = c1    
    return new1, new2


  def CX(self, cfg1, cfg2):
    """
    Implementation of cyclic crossover. Exchange the items occupying the same positions
    in two permutations.
    """
    new1 = self.parent.copy(cfg1)
    new2 = self.parent.copy(cfg2)
    
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)

    s=random.randint(0,len(p1)-1)
    i=s
    indices = []
    while True:
      indices.append(i)
      i = p2.index(p1[i])
      if i==s:
        break

##    print indices
    for j in indices:
      new1[self.name][j]=p2[j]
      new2[self.name][j]=p1[j]
##    print p1, p2
##    print new1
    return (new1, new2)

  def OX1(self, cfg1, cfg2, d=3):
    """
    Ordered Crossover (Davis 1985)
    Two parents exchange subpaths with the same number of nodes while order the remaining
    nodes are maintained in each parent. 
    """
    new1 = self.parent.copy(cfg1)
    new2 = self.parent.copy(cfg2)
    
    p1 = self.get_value(new1)
    p2 = self.get_value(new2)
    
    # Randomly find cut points
    r = random.randint(0, len(p1)-d)    # Todo: treat path as circle i.e. allow cross-boundary cuts
    [p1.remove(i) for i in cfg2[self.name][r:r+d]]
    new1[self.name] = p1[:r]+cfg2[self.name][r:r+d]+p1[r:]
    [p2.remove(i) for i in cfg1[self.name][r:r+d]]
    new2[self.name] = p2[:r]+cfg1[self.name][r:r+d]+p2[r:]

    return new1, new2
    
      
    
    
  def OX3(self, cfg1, cfg2, d=3):
    """
    Ordered crossover variation 3 (Deep 2010)
    Parents have different cut points. (good for tsp which is a cycle?)
    """
    new1 = self.parent.copy(cfg1)
    new2 = self.parent.copy(cfg2)
    
    p1 = self.get_value(new1)
    p2 = self.get_value(new2)
##    print 'PARENTS', p1, p2
    # Randomly find cut points
    r1 = random.randint(0, len(p1)-d)    # Todo: treat path as circle i.e. allow cross-boundary cuts
    r2 = random.randint(0, len(p1)-d)
    [p1.remove(i) for i in cfg2[self.name][r2:r2+d]]
    new1[self.name] = p1[:r1]+cfg2[self.name][r2:r2+d]+p1[r1:]
    [p2.remove(i) for i in cfg1[self.name][r1:r1+d]]
    new2[self.name] = p2[:r2]+cfg1[self.name][r1:r1+d]+p2[r2:]
##    print 'CHILDREN', new1, new2
    return new1, new2


  def EX(self, cfg1, cfg2):
    """
    Edge crossover/recombination (Whitley 1989)
    (inefficient for position representation)
    
    """
##    new1 = self.parent.copy(cfg1)
##    new2 = self.parent.copy(cfg2)
    
    p1 = self.get_value(cfg1)[:]
    p1.append(p1[0])
    p2 =self.get_value(cfg2)[:]
    p2.append(p2[0])

    # Transform two node lists into a single edge map
    edges = {}
    for i in p1:
      edges[i]=set([])
    for i in range(len(p1)-1):
      edges[p1[i]].add(p1[i+1])
      edges[p1[i+1]].add(p1[i])
      edges[p2[i]].add(p2[i+1])
      edges[p2[i+1]].add(p2[i])


    p = [min(p1, key=lambda x: len(edges[x]))]

    while len(p)<len(p1)-1:
      # Get current node
      n = p[-1]
##      print 'CUR', n
      # Update edge map
      [edges[src].discard(n) for src in edges]
##      print 'NEW MAP', edges
      # Choose the node which is connect to current node and has the least usable edges in the edge map
##      print p, edges
##      print p, edges[n]
      if len(edges[n])==0:
        # restart with a node with the least connection
        n = min(edges.keys(), key=lambda x: len(edges[x]))
        continue
##      for dst in edges[n]:
##        print dst, edges[dst]
##      print min(edges[n], key=lambda x: len(edges[x]))
      p.append(min(edges[n], key=lambda x: len(edges[x])))    # todo: randomly break ties in min
    
    new = self.parent.copy(cfg1)
    new[self.name]=p
    return new


      
  def add_difference(self, cfg_dst, b, cfg_b, cfg_c):
    self.apply_swaps(self.scale_swaps(self.swap_dist(cfg_c, cfg_b), b), cfg_dst)
           
       
  
    


  def search_space_size(self):
    return math.factorial(max(1, len(self._items)))

class ScheduleParameter(PermutationParameter):
  def __init__(self, name, items, deps):
    super(ScheduleParameter, self).__init__(name, items)
    self.deps = dict((k, set(v)) for k, v in deps.items())
    log.debug("ScheduleParameter(%s, %s, %s)", repr(name), repr(items),
              repr(deps))
    self._expand_deps()

  def _expand_deps(self):
    '''expand self.deps to include recursive dependencies'''
    fixed_point = False
    while not fixed_point:
      fixed_point = True
      for k in self.deps.keys():
        oldlen = len(self.deps[k])
        for dep in list(self.deps[k]):
          if dep in self.deps:
            self.deps[k].update(self.deps[dep])
        if oldlen != len(self.deps[k]):
          fixed_point = False

    # verify schedule is valid
    items = set(self._items)
    for k, v in self.deps.items():
      if k in v:
        raise Exception("ScheduleParameter('%s') cycle: %s depends on itself" %
                        (self.name, k))

      if v-items:
        raise Exception("ScheduleParameter('%s'): %s is unknown" %
                        (self.name, v-items))

    if set(self.deps.keys())-items:
      raise Exception("ScheduleParameter('%s'): %s is unknown" %
                      (self.name, set(self.deps.keys())-items))


  def is_topologically_sorted(self, values):
    used = set()
    for v in values:
      if v in self.deps and self.deps[v].union(used):
        return False
      used.add(v)
    return True

  def topologically_sorted_depth_first(self, values):
    '''faster but not stable enough'''
    if self.is_topologically_sorted(values):
      return values
    sorted_values = []
    used = set()
    deps = dict((k, sorted(v, key=values.index, reverse=True))
                for k, v in self.deps.items())
    def visit(v):
      if v in used:
        return
      if v in deps:
        for dv in deps[v]:
          visit(dv)
      used.add(v)
      sorted_values.append(v)

    for v in reversed(values):
      visit(v)
    return list(reversed(sorted_values))

  def topologically_sorted(self, values):
    if self.is_topologically_sorted(values):
      return values
    def empty(): pass # token since None may be used by user
    deps = copy.deepcopy(self.deps)
    queue = collections.deque(reversed(values))
    sorted_values = []
    while queue:
      v = queue.popleft()
      if v in deps and deps[v]:
        queue.append(v)
      else:
        for k,d in deps.items():
          d.discard(v)
          if not d:
            del deps[k]
        sorted_values.append(v)

    return list(reversed(sorted_values))

  def normalize(self, cfg):
    self._set(cfg, self.topologically_sorted(self._get(cfg)))


class SelectorParameter(ComplexParameter):
  def __init__(self, name, choices, max_cutoff,
               order_class=PermutationParameter,
               offset_class=LogIntegerParameter):
    super(SelectorParameter, self).__init__(name)
    self.choices = choices
    self.max_cutoff = max_cutoff
    self.order_param = order_class('{0}/order'.format(name), choices)
    self.offset_params = [
        offset_class('{0}/offsets/{1}'.format(name, i), 0, max_cutoff)
        for i in xrange(len(choices) - 1)]

  def sub_parameters(self):
    return [self.order_param] + self.offset_params

  def seed_value(self):
    return {'order' : self.order_param.seed_value(),
            'offsets' : [co.seed_value() for co in self.offset_params]}

  def randomize(self, config):
    random.choice(self.sub_parameters()).randomize(config)

  def selector_iter(self, config):
    '''
    yield (cutoff, choice) pairs
    cutoff will be None on the first value
    '''
    order = config[self.name]['order']
    yield (None, order[0])
    cutoff = 0
    for n, offset in enumerate(config[self.name]['offsets']):
      if offset > 0:
        cutoff += offset
        yield cutoff, order[n + 1]


class ArrayParameter(ComplexParameter):
  def __init__(self, name, count, element_type, *args, **kwargs):
    super(ArrayParameter, self).__init__(name)
    self.count = count
    self.sub_params = [element_type('{0}/{1}'.format(name, i), *args, **kwargs)
                       for i in xrange(count)]

  def sub_parameters(self):
    return self.sub_params

  def seed_value(self):
    return [p.seed_value() for p in self.sub_params]

  def randomize(self, config):
    random.choice(self.sub_parameters()).randomize(config)

class BooleanArrayParameter(ArrayParameter):
  def __init__(self, name, count):
    super(BooleanArrayParameter, self).__init__(name, count, BooleanParameter)


##################

class ManipulatorProxy(object):
  '''
  wrapper around configuration manipulator and config pair
  '''
  def __init__(self, manipulator, cfg):
    self.cfg = cfg
    self.manipulator = manipulator
    self.params = manipulator.parameters_dict()

  def keys(self):
    return self.params.keys()

  def __getitem__(self, k):
    return ParameterProxy(self.params[k], self.cfg)

class ParameterProxy(object):
  '''
  wrapper around parameter and config pair, adds config
  as first argument to all method calls to parameter
  '''
  def __init__(self, param, cfg):
    self.cfg = cfg
    self.param = param

  def __getattr__(self, key):
    '''equivalent of self.param.key(self.cfg, ...)'''
    member = getattr(self.param, key)
    def param_method_proxy(*args, **kwargs):
      return member(self.cfg, *args, **kwargs)
    if callable(member):
      return param_method_proxy
    else:
      # we should only hit this for key == 'name'
      return member



