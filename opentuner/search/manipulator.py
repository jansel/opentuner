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
from pprint import pprint
from collections import defaultdict

class ConfigurationManipulatorBase(object):
  '''
  abstract interface for objects used by search techniques to mutate
  configurations
  '''
  __metaclass__ = abc.ABCMeta

  def validate(self, config):
    '''is the given config valid???'''
    return all(map(lambda x: x.validate(config), self.parameters(config)))

  def set_search_driver(self, search_driver):
    pass
  
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
    return self.params
  
  def hash_config(self, config):
    '''produce unique hash value for the given config'''
    m = hashlib.sha256()
    params = list(self.parameters(config))
    params.sort(key=lambda x: x.name)
    for i, p in enumerate(params):
      m.update(p.name)
      m.update(p.hash_value(config))
      m.update(str(i))
      m.update("|")
    return m.hexdigest()

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
  def hash_value(self, config):
    '''produce unique hash for this value in the config'''
    return

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
  
class ComplexParameter(Parameter):
  '''
  a non-cartesian parameter conforming to a maze interface with a variable
  number of directions that can be taken from any given point
  '''
  __metaclass__ = abc.ABCMeta
  @abc.abstractmethod
  def possible_directions(self, config):
    '''number legal directions that can be taken from the current position'''
    return 1

  @abc.abstractmethod
  def step(self, config, direction, magnitute=0.5):
    '''
    change the given configuration by taking a step in the given direction
    magnitude ranges between 0 and 1 and 0.5 should be a reasonable step size
    '''
    pass

class NumericParameter(PrimativeParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    '''min/max are inclusive'''
    super(NumericParameter, self).__init__(name, **kwargs)
    #second so value_type is initialized
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
    kwargs['value_type']=int
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








