#!/usr/bin/python
import abc
import copy
import itertools
import logging
import math
import os
import random
import subprocess
import sys
import tempfile
import hashlib
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
    return all(map(_.validate(config), self.parameters(config)))

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

  def __init__(self, params=[], config_type=dict, **kwargs):
    self.params = list(params)
    self.config_type = config_type
    self.search_driver = None
    super(ConfigurationManipulator, self).__init__(**kwargs)

  def add_parameter(self, p):
    p.set_parent(self)
    self.params.append(p)

  def set_search_driver(self, search_driver):
    self.search_driver = search_driver

  def seed_config(self):
    '''produce a fixed seed configuration'''
    cfg = self.config_type()
    for p in self.params:
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
      m.update(p.name)
      m.update(p.hash_value(config))
      m.update(str(i))
      m.update("|")
    return m.hexdigest()

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

  def set_parent(self, manipulator):
    self.parent = manipulator

  def validate(self, config):
    '''is the given config valid???'''
    return True

  def is_primative(self, ignored = None):
    return isinstance(self, PrimativeParameter)

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

class PrimativeParameter(Parameter):
  '''
  a single dimension in a cartesian space, with a minimum and a maximum value
  '''
  __metaclass__ = abc.ABCMeta

  def __init__(self, name, value_type=int, **kwargs):
    self.value_type = value_type
    super(PrimativeParameter, self).__init__(name, **kwargs)

  def hash_value(self, config):
    '''produce unique hash for this value in the config'''
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

class NumericParameter(PrimativeParameter):
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
    config[self.name] = self.value_type(value)

  def get_value(self, config):
    return config[self.name]

  def legal_range(self, config):
    return (self.min_value, self.max_value)


class IntegerParameter(NumericParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    '''min/max are inclusive'''
    kwargs['value_type'] = int
    super(IntegerParameter, self).__init__(name, min_value, max_value, **kwargs)

  def randomize(self, config):
    self.set_value(config, random.randint(*self.legal_range(config)))

class FloatParameter(NumericParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    '''min/max are inclusive'''
    kwargs['value_type']=float
    super(FloatParameter, self).__init__(name, min_value, max_value, **kwargs)

  def randomize(self, config):
    self.set_value(config, random.uniform(*self.legal_range(config)))

##################

class ComplexParameter(Parameter):
  '''
  a non-cartesian parameter that can't be manipulated directly, but has a set
  of user defined manipulation functions
  '''

  def _to_storage_type(self, val):
    '''hook to support transformation applied while stored'''
    return val

  def _from_storage_type(self, sval):
    '''hook to support transformation applied while stored'''
    return sval

  def _get(self, config):
    '''hook to support different storage structures'''
    return self._from_storage_type(config[self.name])

  def _set(self, config, v):
    '''hook to support different storage structures'''
    config[self.name] = self._to_storage_type(v)

  def copy_value(self, src, dst):
    '''copy the value of this parameter from src to dst config'''
    self._set(dst, copy.deepcopy(self._get(src)))

  def same_value(self, cfg1, cfg2):
    '''test if cfg1 and cfg2 have the same value of this parameter'''
    return self._get(cfg1) == self._get(cfg2)

  def hash_value(self, config):
    '''produce unique hash for this value in the config'''
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
      self.randomize()

  def manipulators(self, config):
    '''
    a list of manipulator functions to change this valid in the config
    manipulators must be functions that take a config and change it in place

    default implementation just has randomize as only operation
    '''
    return [self.randomize]

  @abc.abstractmethod
  def randomize(self, config):
    '''randomize this value without taking into account the current position'''
    pass

  @abc.abstractmethod
  def seed_value(self):
    '''some legal value of this parameter (for creating initial configs)'''
    return


class SwitchParameter(ComplexParameter):
  '''
  a switch parameter is an unordered collection of options with no implied
  correlation between the choices, choices are range(option_count)
  '''
  def __init__(self, name, option_count):
    self.option_count = option_count
    super(SwitchParameter, self).__init__(name)

  def randomize(self, config):
    self._set(config, self.seed_value())

  def seed_value(self):
    return random.randrange(self.option_count)


class EnumParameter(SwitchParameter):
  '''
  same as a SwitchParameter but choices are taken from an arbitrarily typed list
  '''
  def __init__(self, name, options):
    self.int_to_opt = list(options)
    self.opt_to_int = dict([(v, idx) for idx, v in enumerate(options)])
    assert len(self.int_to_opt) == len(self.opt_to_int) #duplicate options?
    super(EnumParameter, self).__init__(name, option_count=len(options))

  def _to_storage_type(self, val):
    return super(EnumParameter)._to_storage_type(self.int_to_opt[val])

  def _from_storage_type(self, sval):
    return self.opt_to_int[super(EnumParameter)._from_storage_type(sval)]


##################

class ManipulatorProxy(object):
  '''
  wrapper around configuration manipulator and config pair
  '''
  def __init__(self, manipulator, cfg):
    self.cfg = cfg
    self.manipulator = manipulator
    self.params = manipulator.parameters_dict(self.cfg)

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



