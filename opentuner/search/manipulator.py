# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab autoindent smarttab
import abc
import collections
import copy
import hashlib
import json
import logging
import math
import os
import pickle
import random
from fn import _
import argparse
from datetime import datetime
import numpy
import inspect
import sys

log = logging.getLogger(__name__)
argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--list-params', '-lp',
                       help='list available parameter classes')


class ConfigurationManipulatorBase(object):
  """
  abstract interface for objects used by search techniques to mutate
  configurations
  """
  __metaclass__ = abc.ABCMeta

  # List of file formats, which can be extended by subclasses. Used in
  # write_to_file() and load_from_file().  Objects in list must define
  # load(fd) and dump(cfg, fd).
  FILE_FORMATS = {'default': json, 'json': json,
                  'pickle': pickle, 'pk': pickle}

  def validate(self, config):
    """is the given config valid???"""
    return all(map(_.validate(config), self.parameters(config)))

  def normalize(self, config):
    """mutate config into canonical form"""
    for param in self.parameters(config):
      param.normalize(config)

  def set_search_driver(self, search_driver):
    """called exactly once during setup"""
    pass

  def copy(self, config):
    """produce copy of config"""
    return copy.deepcopy(config)

  def parameters_dict(self, config):
    """convert self.parameters() to a dictionary by name"""
    return dict([(p.name, p) for p in self.parameters(config)])

  def param_names(self, *args):
    """return union of parameter names in args"""
    return sorted(reduce(set.union,
                         [set(map(_.name, self.parameters(cfg)))
                          for cfg in args]))

  def linear_config(self, a, cfg_a, b, cfg_b, c, cfg_c):
    """return a configuration that is a linear combination of 3 other configs"""
    dst = self.copy(cfg_a)
    dst_params = self.proxy(dst)
    for k in self.param_names(dst, cfg_a, cfg_b, cfg_c):
      dst_params[k].set_linear(a, cfg_a, b, cfg_b, c, cfg_c)
    return dst

  def _get_serializer(self, filename, format=None):
    """
    Extract the correct file format serializer from self.FILE_FORMATS.
    Guess the format by extension if one is not given.
    """
    if format is None:
      format = os.path.splitext(filename)[1].lower().replace('.', '')
    if format not in self.FILE_FORMATS:
      serializer = self.FILE_FORMATS['default']
      if len(self.FILE_FORMATS) > 1:
        log.warning('Unknown file format "%s", using "%s" instead', format,
                    serializer.__name__)
    else:
      serializer = self.FILE_FORMATS[format]
    return serializer

  def save_to_file(self, cfg, filename, format=None):
    """
    Write cfg to filename.  Guess the format by extension if one is not given.
    """
    with open(filename, 'wb') as fd:
      self._get_serializer(filename, format).dump(cfg, fd)

  def load_from_file(self, filename, format=None):
    """
    Read cfg from filename.  Guess the format by extension if one is not given.
    """
    with open(filename, 'rb') as fd:
      return self._get_serializer(filename, format).load(fd)

  def proxy(self, cfg):
    return ManipulatorProxy(self, cfg)

  @abc.abstractmethod
  def random(self):
    """produce a random initial configuration"""
    return

  @abc.abstractmethod
  def parameters(self, config):
    """return a list of of Parameter objects"""
    return list()

  @abc.abstractmethod
  def hash_config(self, config):
    """produce unique hash value for the given config"""
    return


class ConfigurationManipulator(ConfigurationManipulatorBase):
  """
  a configuration manipulator using a fixed set of parameters and storing
  configs in a dict-like object
  """

  def __init__(self, params=None, config_type=dict, seed_config=None, **kwargs):
    if params is None:
      params = []
    self.params = list(params)
    self.config_type = config_type
    self.search_driver = None
    self._seed_config = seed_config
    super(ConfigurationManipulator, self).__init__(**kwargs)
    for p in self.params:
      p.parent = self

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
    """produce a fixed seed configuration"""
    if self._seed_config:
      cfg = copy.deepcopy(self._seed_config)
    else:
      cfg = self.config_type()
      for p in self.params:
        if not isinstance(p.name, str) or '/' not in p.name:
          cfg[p.name] = p.seed_value()
    return cfg

  def random(self):
    """produce a random configuration"""
    cfg = self.seed_config()
    for p in self.parameters(cfg):
      p.randomize(cfg)
    return cfg

  def parameters(self, config):
    """return a list of Parameter objects"""
    if type(config) is not self.config_type:
      log.error("wrong type, expected %s got %s",
                str(self.config_type),
                str(type(config)))
      raise TypeError()
    return self.params

  def hash_config(self, config):
    """produce unique hash value for the given config"""
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
    """estimate the size of the search space, not precise"""
    return reduce(_ * _, [x.search_space_size() for x in self.params])

  def difference(self, cfg1, cfg2):
    cfg = self.copy(cfg1)
    for param in self.parameters(cfg1):
      if param.is_primitive(cfg1):
        # TODO: check range
        param.set_value(cfg, param.get_value(cfg1) - param.get_value(cfg2))
      else:
        pass
    return cfg

  def applySVs(self, cfg, sv_map, args, kwargs):
    """
    Apply operators to each parameter according to given map. Updates cfg.
    Parameters with no operators specified are not updated. 
    cfg: configuration data
    sv_map: python dict that maps string parameter name to class method name
    arg_map: python dict that maps string parameter name to class method arguments
    """
    # TODO: check consistency between sv_map and cfg
    param_dict = self.parameters_dict(cfg)
    for pname in self.param_names(cfg):
      param = param_dict[pname]
      getattr(param, sv_map[pname])(cfg, *args[pname], **kwargs[pname])


class Parameter(object):
  """
  abstract base class for parameters in a ConfigurationManipulator
  """
  __metaclass__ = abc.ABCMeta

  def __init__(self, name):
    self.name = name
    self.parent = None
    super(Parameter, self).__init__()

  def _to_storage_type(self, val):
    """hook to support transformation applied while stored"""
    return val

  def _from_storage_type(self, sval):
    """hook to support transformation applied while stored"""
    return sval

  def _read_node(self, config):
    """hook to support different storage structures"""
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
    """hook to support different storage structures"""
    node, part = self._read_node(config)
    return self._from_storage_type(node[part])

  def _set(self, config, v):
    """hook to support different storage structures"""
    node, part = self._read_node(config)
    node[part] = self._to_storage_type(v)

  def set_parent(self, manipulator):
    self.parent = manipulator

  def validate(self, config):
    """is the given config valid???"""
    return True

  def is_primitive(self, ignored=None):
    return isinstance(self, PrimitiveParameter)

  def is_permutation(self, ignored=None):
    return isinstance(self, PermutationParameter)

  def manipulators(self, config):
    """
    a list of manipulator functions to change this value in the config
    manipulators must be functions that take a config and change it in place

    default implementation just has randomize as only operation
    """
    return [self.randomize]

  def normalize(self, config):
    """
    mutate this parameter into a canonical form
    """
    pass

  def sub_parameters(self):
    """
    additional parameters added with this parameter
    """
    return []

  @abc.abstractmethod
  def randomize(self, config):
    """randomize this value without taking into account the current position"""
    pass

  @abc.abstractmethod
  def seed_value(self):
    """some legal value of this parameter (for creating initial configs)"""
    return

  @abc.abstractmethod
  def copy_value(self, src, dst):
    """copy the value of this parameter from src to dst config"""
    pass

  @abc.abstractmethod
  def same_value(self, cfg1, cfg2):
    """test if cfg1 and cfg2 have the same value of this parameter"""
    return

  @abc.abstractmethod
  def hash_value(self, config):
    """produce unique hash for this value in the config"""
    return

  @abc.abstractmethod
  def set_linear(self, cfg_dst, a, cfg_a, b, cfg_b, c, cfg_c):
    """set this value to a*cfg_a + b*cfg_b, + c*cfg_c"""
    pass

  def search_space_size(self):
    return 1

  # Stochastic variators 
  def sv_mix(self, dest, cfgs, ratio,  *args, **kwargs):
    """ 
    Stochastically recombine values from multiple parent configurations and save the 
    resulting value in dest. 
    cfgs: list of configuration data (dict)
    ratio: list of floats
    """
    assert len(cfgs)==len(ratio)
    r = random.random()
    c = numpy.array(ratio, dtype=float)/sum(ratio)
    for i in range(len(c)):
      if r < sum(c[:i+1]):
        self.copy_value(dest, cfgs[i])
        break

  def sv_swarm(self, current, cfg1, cfg2, c, c1, c2, *args, **kwargs):
    """
    Stochastically 'move' value in current configuration towards those in two other configurations. 
    current, cfg1, cfg2: configuration data (dict)
    c, c1, c2: float
    """
    self.sv_mix(current, [current, cfg1, cfg2], [c, c1, c2])  # default to probablistic treatment

class PrimitiveParameter(Parameter):
  """
  a single dimension in a cartesian space, with a minimum and a maximum value
  """
  __metaclass__ = abc.ABCMeta

  def __init__(self, name, value_type=float, **kwargs):
    self.value_type = value_type
    super(PrimitiveParameter, self).__init__(name, **kwargs)

  def hash_value(self, config):
    """produce unique hash for this value in the config"""
    self.normalize(config)
    return hashlib.sha256(repr(self.get_value(config))).hexdigest()

  def copy_value(self, src, dst):
    """copy the value of this parameter from src to dst config"""
    self.set_value(dst, self.get_value(src))

  def same_value(self, cfg1, cfg2):
    """test if cfg1 and cfg2 have the same value of this parameter"""
    return self.get_value(cfg1) == self.get_value(cfg2)

  def is_integer_type(self):
    """true if self.value_type can only represent integers"""
    return self.value_type(0) == self.value_type(0.1)

  def get_unit_value(self, config):
    """get_value scaled such that range is between 0.0 and 1.0"""
    low, high = self.legal_range(config)
    if self.is_integer_type():
      # account for rounding
      low -= 0.4999
      high += 0.4999
    val = self.get_value(config)
    if low < high:
      return float(val - low) / float(high - low)
    else:
      if low > high:
        log.warning('invalid range for parameter %s, %s to %s',
                    self.name, low, high)
      # only a single legal value!
      return 0.0

  def set_unit_value(self, config, unit_value):
    """set_value scaled such that range is between 0.0 and 1.0"""
    assert 0.0 <= unit_value and unit_value <= 1.0
    low, high = self.legal_range(config)
    if self.is_integer_type():
      # account for rounding
      low -= 0.4999
      high += 0.4999
    if low < high:
      val = unit_value * float(high - low) + low
      if self.is_integer_type():
        val = round(val)
      val = max(low, min(val, high))
      self.set_value(config, self.value_type(val))

  def set_linear(self, cfg_dst, a, cfg_a, b, cfg_b, c, cfg_c):
    """set this value to a*cfg_a + b*cfg_b, + c*cfg_c"""
    va = self.get_unit_value(cfg_a)
    vb = self.get_unit_value(cfg_b)
    vc = self.get_unit_value(cfg_c)
    v = a * va + b * vb + c * vc
    v = max(0.0, min(v, 1.0))

    self.set_unit_value(cfg_dst, v)

  def normal_mutation(self, cfg, sigma=0.1, *args, **kwargs):
    """
    apply normally distributed noise to the value of this parameter in cfg

    sigma is the stddev of the normal distribution on a unit scale (search
    space is of size 1)
    """
    v = self.get_unit_value(cfg)
    v += random.normalvariate(0.0, sigma)
    # handle boundary cases by reflecting off the edge
    if v < 0.0:
      v *= -1.0
    if v > 1.0:
      v = 1.0 - (v % 1)
    self.set_unit_value(cfg, v)

  def manipulators(self, config):
    """
    a list of manipulator functions to change this value in the config
    manipulators must be functions that take a config and change it in place

    for primitive params default implementation is uniform random and normal
    """
    return [self.randomize, self.normal_mutation]

  @abc.abstractmethod
  def set_value(self, config, value):
    """assign this value in the given configuration"""
    pass

  @abc.abstractmethod
  def get_value(self, config):
    """retrieve this value from the given configuration"""
    return 0

  @abc.abstractmethod
  def legal_range(self, config):
    """return the legal range for this parameter, inclusive"""
    return 0, 1


class NumericParameter(PrimitiveParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    """min/max are inclusive"""
    assert min_value <= max_value
    super(NumericParameter, self).__init__(name, **kwargs)
    # after super call so self.value_type is initialized
    self.min_value = self.value_type(min_value)
    self.max_value = self.value_type(max_value)

  def seed_value(self):
    """some legal value of this parameter (for creating initial configs)"""
    return self.min_value

  def set_value(self, config, value):
    assert value >= self.min_value
    assert value <= self.max_value
    self._set(config, value)

  def get_value(self, config):
    return self._get(config)

  def legal_range(self, config):
    return self.min_value, self.max_value

  def difference(self, cfg, cfg1, cfg2):
    v = self.get_value(cfg2) - self.get_value(cfg1)
    v = max(self.min_value, min(self.max_value, v))
    self.set_value(cfg, v)

  def scale(self, cfg, k):
    v = self.get_value(cfg) * k
    v = max(self.min_value, min(self.max_value, v))
    self.set_value(cfg, v)

  def sum(self, cfg, *cfgs):
    v = sum([self.get_value(c) for c in cfgs])
    v = max(self.min_value, min(self.max_value, v))
    self.set_value(cfg, v)

  def randomize(self, config):
    if self.is_integer_type():
      self.set_value(config, random.randint(*self.legal_range(config)))
    else:
      self.set_value(config, random.uniform(*self.legal_range(config)))

  def search_space_size(self):
    if self.value_type is float:
      return 2 ** 32
    else:
      return self.max_value - self.min_value + 1  # inclusive range

  def sv_mutate(self, cfg, mchoice='normal_mutation', *args, **kwargs):
    getattr(self, mchoice)(cfg, *args, **kwargs)


class IntegerParameter(NumericParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    """min/max are inclusive"""
    kwargs['value_type'] = int
    super(IntegerParameter, self).__init__(name, min_value, max_value, **kwargs)

  def sv_swarm(self, current, cfg1, cfg2, c=1, c1=0.5,
               c2=0.5, velocity=0, sigma=0.2, *args, **kwargs):
    """ Updates current and returns new velocity """
    vmin, vmax = self.legal_range(current)
    k = vmax - vmin
    v = velocity * c + (self.get_value(cfg1) - self.get_value(
      current)) * c1 * random.random() + (self.get_value(
      cfg2) - self.get_value(current)) * c2 * random.random()
    # Map velocity to continuous space with sigmoid
    s = k / (1 + numpy.exp(-v)) + vmin
    # Add Gaussian noise
    p = random.gauss(s, sigma * k)
    # Discretize and bound 
    p = int(min(vmax, max(round(p), vmin)))
    self.set_value(current, p)
    return v


class FloatParameter(NumericParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    """min/max are inclusive"""
    kwargs['value_type'] = float
    super(FloatParameter, self).__init__(name, min_value, max_value, **kwargs)

  def sv_swarm(self, current, cfg1, cfg2, c=1, c1=0.5,
               c2=0.5, velocity=0, *args, **kwargs):
    vmin, vmax = self.legal_range(current)
    v = velocity * c + (self.get_value(cfg1) - self.get_value(
      current)) * c1 * random.random() + (self.get_value(
      cfg2) - self.get_value(current)) * c2 * random.random()
    p = self.get_value(current) + v
    p = min(vmax, max(p, vmin))
    self.set_value(current, p)
    return v


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


class LogIntegerParameter(ScaledNumericParameter, FloatParameter):
  """
  a numeric parameter that is searched on a log scale, but stored without
  scaling
  """

  def _scale(self, v):
    return math.log(v + 1.0 - self.min_value, 2.0)

  def _unscale(self, v):
    v = 2.0 ** v - 1.0 + self.min_value
    v = int(round(v))
    return v

  def legal_range(self, config):
    low, high = NumericParameter.legal_range(self, config)
    # increase the bounds account for rounding
    return self._scale(low - 0.4999), self._scale(high + 0.4999)


class LogFloatParameter(ScaledNumericParameter, FloatParameter):
  """
  a numeric parameter that is searched on a log scale, but stored without
  scaling
  """

  def _scale(self, v):
    return math.log(v + 1.0 - self.min_value, 2.0)

  def _unscale(self, v):
    v = 2.0 ** v - 1.0 + self.min_value
    return v


class PowerOfTwoParameter(ScaledNumericParameter, IntegerParameter):
  """An integer power of two, with a given min and max value"""

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
    return 2 ** int(v)

  def legal_range(self, config):
    return int(math.log(self.min_value, 2)), int(math.log(self.max_value, 2))

  def search_space_size(self):
    return int(math.log(super(PowerOfTwoParameter, self).search_space_size(), 2))


# #################

class ComplexParameter(Parameter):
  """
  a non-cartesian parameter that can't be manipulated directly, but has a set
  of user defined manipulation functions
  """

  def copy_value(self, src, dst):
    """copy the value of this parameter from src to dst config"""
    self._set(dst, copy.deepcopy(self._get(src)))

  def same_value(self, cfg1, cfg2):
    """test if cfg1 and cfg2 have the same value of this parameter"""
    return self._get(cfg1) == self._get(cfg2)

  def hash_value(self, config):
    """produce unique hash for this value in the config"""
    self.normalize(config)
    return hashlib.sha256(repr(self._get(config))).hexdigest()

  def get_value(self, config):
    return self._get(config)

  def set_value(self, config, value):
    self._set(config, value)

  def set_linear(self, cfg_dst, a, cfg_a, b, cfg_b, c, cfg_c):
    """
    set this value to a*cfg_a + b*cfg_b + c*cfg_c

    this operation is not possible in general with complex parameters but
    we make an attempt to "fake" it for common use cases
    """
    # attempt to normalize order, we prefer a==1.0
    if a != 1.0 and b == 1.0:  # swap a and b
      a, cfg_a, b, cfg_b = b, cfg_b, a, cfg_a
    if a != 1.0 and c == 1.0:  # swap a and c
      a, cfg_a, c, cfg_c = c, cfg_c, a, cfg_a

    # attempt to normalize order, we prefer b==-c
    if b < c:  # swap b and c
      b, cfg_b, c, cfg_c = c, cfg_c, b, cfg_b
    if b != -c and a == -c:  # swap a and c
      a, cfg_a, c, cfg_c = c, cfg_c, a, cfg_a

    if a == 1.0 and b == -c:
      self.copy_value(cfg_a, cfg_dst)
      self.add_difference(cfg_dst, b, cfg_b, cfg_c)
    else:
      # TODO: should handle more cases
      self.randomize()

  def add_difference(self, cfg_dst, scale, cfg_b, cfg_c):
    """
    add the difference cfg_b-cfg_c to cfg_dst

    this is the key operation used in differential evolution
    and some simplex techniques

    this operation is not possible in general with complex parameters but
    we make an attempt to "fake" it
    """
    if not self.same_value(cfg_b, cfg_c):
      self.randomize(cfg_dst)

  def sv_mutate(self, cfg, mchoice='randomize', *args, **kwargs):
    getattr(self, mchoice)(cfg, *args, **kwargs)

  @abc.abstractmethod
  def randomize(self, config):
    """randomize this value without taking into account the current position"""
    pass

  @abc.abstractmethod
  def seed_value(self):
    """some legal value of this parameter (for creating initial configs)"""
    return


class BooleanParameter(ComplexParameter):
  def manipulators(self, config):
    return [self.flip]

  def get_value(self, config):
    return self._get(config)

  def set_value(self, config, value):
    self._set(config, value)

  def randomize(self, config):
    self._set(config, self.seed_value())

  def seed_value(self):
    return random.choice((True, False))

  def flip(self, config):
    self._set(config, not self._get(config))

  def search_space_size(self):
    return 2

  def sv_swarm(self, current, cfg1, cfg2, c=1, c1=0.5,
               c2=0.5, velocity=0, *args, **kwargs):
    """ 
    Updates current and returns new velocity.
    current, cfg1, cfg2 are all configuration data;
    c, c1, c2, velocity are floats;
    Return updated velocities for each element in the BooleanArrayParameter.
    """
    v = velocity * c + (self.get_value(cfg1) - self.get_value(
      current)) * c1 * random.random() + (self.get_value(
      cfg2) - self.get_value(current)) * c2 * random.random()
    # Map velocity to continuous space with sigmoid
    s = 1 / (1 + numpy.exp(-v))
    # Decide position randomly  
    p = (s - random.random()) > 0
    self.set_value(current, p)
    return v


class SwitchParameter(ComplexParameter):
  """
  a switch parameter is an unordered collection of options with no implied
  correlation between the choices, choices are range(option_count)
  """

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
  """
  same as a SwitchParameter but choices are taken from an arbitrarily typed list
  """

  def __init__(self, name, options):
    super(EnumParameter, self).__init__(name)
    self.options = list(options)

  def randomize(self, config):
    self._set(config, random.choice(self.options))

  def seed_value(self):
    return random.choice(self.options)

  def search_space_size(self):
    return max(1, len(self.options))

  def sv_mutate(self, cfg, *args, **kwargs):
    self.randomize(cfg)


class PermutationParameter(ComplexParameter):
  def __init__(self, name, items):
    super(PermutationParameter, self).__init__(name)
    self._items = list(items)
    self.size = len(items)

  def randomize(self, config):
    random.shuffle(self._get(config))
    self.normalize(config)

  def small_random_change(self, config):
    cfg_item = self._get(config)
    for i in xrange(1, len(cfg_item)):
      if random.random() < 0.25:
        # swap
        cfg_item[i - 1], cfg_item[i] = cfg_item[i], cfg_item[i - 1]
    self.normalize(config)

  def seed_value(self):
    return list(self._items)  # copy

  def manipulators(self, config):
    return [self.randomize, self.small_random_change]

  def get_value(self, config):
    return self._get(config)

  def set_value(self, config, value):
    self._set(config, value)

  def search_space_size(self):
    return math.factorial(max(1, len(self._items)))

  # Stochastic Variator     
  def sv_mutate(self, cfg, mchoice='random_swap', *args, **kwargs):
    getattr(self, mchoice)(cfg, cfg, *args, **kwargs)

  def sv_cross(self, new, cfg1, cfg2, xchoice='OX1', strength=0.3, *args,
               **kwargs):
    dd = int(round(self.size * strength))
    if dd < 1:
      log.warning('Crossover length too small. Cannot create new solution.')
    if dd >= self.size:
      log.warning('Crossover length too big. Cannot create new solution.')
    getattr(self, xchoice)(new, cfg1, cfg2, d=dd, *args, **kwargs)

  def sv_swarm(self, current, cfg1, cfg2, xchoice='OX1', c=1,
               c1=0.5, c2=0.5, strength=0.3, velocity=0, *args, **kwargs):
    if random.uniform(0, 1) > c:
      if random.uniform(0, 1) < c1:
        # Select crossover operator
        self.sv_cross(current, current, cfg1, xchoice, strength)
      else:
        self.sv_cross(current, current, cfg2, xchoice, strength)


  # swap-based operators
  def random_swap(self, dest, cfg, *args, **kwargs):
    """
    swap a random pair of items seperated by distance d
    """
    p = self.get_value(cfg)[:]
    r = random.randint(0, len(p) - 1)
    s = random.randint(0, len(p) - 1)
    v1 = p[r]
    v2 = p[s]
    p[r] = v2
    p[s] = v1
    self.set_value(dest, p)

  def random_invert(self, dest, cfg, strength=0.3, *args, **kwargs):
    """
    randomly invert a length-d subsection of the permutation
    """
    p = self.get_value(cfg)[:]
    d = int(round(len(p) * strength))
    r = random.randint(0, len(p) - d)
    subpath = p[r:r + d][:]
    subpath.reverse()
    p[r:r + d] = subpath
    self.set_value(dest, p)


  # Crossover operators
  def PX(self, dest, cfg1, cfg2, d):
    """
    Partition crossover (Whitley 2009?)
    Change the order of items up to c1 in cfg1 according to their order in cfg2.
    """

    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    c1 = random.randint(0, len(p1))
    self.set_value(dest, sorted(p1[:c1], key=lambda x: p2.index(x)) + p1[c1:])

  def PMX(self, dest, cfg1, cfg2, d):
    """
    Partially-mapped crossover Goldberg & Lingle (1985)
    """

    p1 = self.get_value(cfg1)[:]
    p2 = self.get_value(cfg2)[:]

    r = random.randint(0, len(p1) - d)
    c1 = p1[r:r + d]
    c2 = p2[r:r + d]
    # Construct partial map
    pm = dict([(c1[i], c2[i]) for i in range(d)])
    agenda = c1[:]
    while agenda != []:
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
    pm2 = dict([(v, k) for k, v in pm.items()])
    # Fix conflicts
    for k in pm:
      p2[p2.index(k)] = pm[k]
    for k in pm2:
      p1[p1.index(k)] = pm2[k]
      # Cross over
    p1[r:r + d] = c2
    p2[r:r + d] = c1

    self.set_value(dest, p1)


  def CX(self, dest, cfg1, cfg2, d):
    """
    Implementation of cyclic crossover. Exchange the items occupying the same positions
    in two permutations.
    """
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    p = p1[:]

    s = random.randint(0, len(p1) - 1)
    i = s
    indices = []
    while True:
      indices.append(i)
      i = p2.index(p1[i])
      if i == s:
        break

    for j in indices:
      p[j] = p2[j]

    self.set_value(dest, p)

  def OX1(self, dest, cfg1, cfg2, d):
    """
    Ordered Crossover (Davis 1985)
    Two parents exchange subpaths with the same number of nodes while order the remaining
    nodes are maintained in each parent. 
    """
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    c1 = p1[:]
    c2 = p2[:]
    # Randomly find cut points
    r = random.randint(0, len(
      p1) - d)  # Todo: treat path as circle i.e. allow cross-boundary cuts
    [c1.remove(i) for i in p2[r:int(r + d)]]
    self.set_value(dest, c1[:r] + p2[r:r + d] + c1[r:])

  def OX3(self, dest, cfg1, cfg2, d):
    """
    Ordered crossover variation 3 (Deep 2010)
    Parents have different cut points. (good for tsp which is a cycle?)
    """
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    c1 = p1[:]
    c2 = p2[:]
    # Randomly find cut points
    # Todo: treat path as circle i.e. allow cross-boundary cuts
    r1 = random.randint(0, len(p1) - d)
    r2 = random.randint(0, len(p1) - d)
    [c1.remove(i) for i in p2[r2:r2 + d]]
    self.set_value(dest, c1[:r1] + p2[r2:r2 + d] + c1[r1:])

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
    """expand self.deps to include recursive dependencies"""
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

      if v - items:
        raise Exception("ScheduleParameter('%s'): %s is unknown" %
                        (self.name, v - items))

    if set(self.deps.keys()) - items:
      raise Exception("ScheduleParameter('%s'): %s is unknown" %
                      (self.name, set(self.deps.keys()) - items))


  def is_topologically_sorted(self, values):
    used = set()
    for v in values:
      if v in self.deps and self.deps[v].union(used):
        return False
      used.add(v)
    return True

  def topologically_sorted_depth_first(self, values):
    """faster but not stable enough"""
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
    deps = copy.deepcopy(self.deps)
    queue = collections.deque(reversed(values))
    sorted_values = []
    while queue:
      v = queue.popleft()
      if v in deps and deps[v]:
        queue.append(v)
      else:
        for k, d in deps.items():
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
    return {'order': self.order_param.seed_value(),
            'offsets': [co.seed_value() for co in self.offset_params]}

  def randomize(self, config):
    random.choice(self.sub_parameters()).randomize(config)

  def selector_iter(self, config):
    """
    yield (cutoff, choice) pairs
    cutoff will be None on the first value
    """
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

    self.sub_params = [
      element_type('{0}/{1}'.format(name, i), *args[i], **kwargs[i])
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

  def sv_swarm(self, *args, **kwargs):
    #TODO
    pass

  def sv_select_cross(self, *args, **kwargs):
    #TODO
    pass

  def sv_cross(self, *args, **kwargs):
    #TODO
    pass

  def sv_double_cross(self, *args, **kwargs):
    #TODO
    pass


class IntegerArrayParameter(ArrayParameter):
  def __init__(self, name, min_values, max_values):
    assert len(min_values) == len(max_values)
    super(IntegerArrayParameter, self).__init__(name, len(min_values),
                                                IntegerParameter,
                                                min_value=min_values,
                                                max_value=max_values)

  def sv_swarm(self, *args, **kwargs):
    #TODO
    pass

  def sv_select_cross(self, *args, **kwargs):
    #TODO
    pass

  def sv_cross(self, *args, **kwargs):
    #TODO
    pass

  def sv_double_cross(self, *args, **kwargs):
    #TODO
    pass


class Array(ComplexParameter):
  """ Alternative implementation for ArrayParameter."""
  #TODO: constraints? (upper & lower bound etc) 
  def __init__(self, name, size):
    super(Array, self).__init__(name)
    self.size = size

  def sv_cross(self, dest, cfg1, cfg2, strength=0.3, *args, **kwargs):
    d = int(round(self.size * strength))
    if d < 1:
      log.debug('Crossover length too small. Cannot create new solution.')
    if d >= self.size:
      log.debug('Crossover length too big. Cannot create new solution.')
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    r = random.randint(0, len(
      p1) - d)  # Todo: treat path as circle i.e. allow cross-boundary cuts
    p = numpy.concatenate([p1[:r], p2[r:r + d], p1[r + d:]])
    self.set_value(dest, p)

  def sv_swarm(self, current, cfg1, cfg2, c=1, c1=0.5,
               c2=0.5, velocity=0, strength=0.3, *args, **kwargs):
    if random.uniform(0, 1) > c:
      if random.uniform(0, 1) < c1:
        # Select crossover operator
        self.sv_cross(current, current, cfg1, strength)
      else:
        self.sv_cross(current, current, cfg2, strength)

  def get_value(self, config):
    return self._get(config)

  def set_value(self, config, value):
    self._set(config, value)


class BooleanArray(Array):
  def sv_swarm_parallel(self, current, cfg1, cfg2, c=1,
                        c1=0.5, c2=0.5, velocities=0):
    """ 
    Updates current and returns the updated velocity array.
    current, cfg1, cfg2 are configuration data;
    c, c1, c2 are floats;
    velocities is a numpy array of floats;
    """
    vs = velocities * c + (self.get_value(cfg1) - self.get_value(
      current)) * c1 * random.random() + (self.get_value(
      cfg2) - self.get_value(current)) * c2 * random.random()
    # Map velocity to continuous space with sigmoid
    ss = 1 / (1 + numpy.exp(-vs))
    # Decide position randomly  
    ps = (ss - numpy.random.rand(1, self.size)) > 0
    self.set_value(current, ps)
    return vs

  def randomize(self, config):
    value = numpy.random.rand(1, self.size) > 0.5
    self._set(config, value)

  def seed_value(self):
    return numpy.random.rand(1, self.size) > 0.5


class FloatArray(Array):
  def __init__(self, fmax, fmin):
    assert fmax == fmin
    super(FloatArray, self).__init__(name, len(fmax))
    self.fmax = fmax
    self.fmin = fmin

  def randomize(self, config):
    value = numpy.random.rand(1, self.size) * (
    self.fmax - self.fmin) + self.fmin
    self._set(config, value)

  def seed_value(self):
    value = numpy.random.rand(1, self.size) * (
    self.fmax - self.fmin) + self.fmin
    return value

  def sv_swarm_parallel(self, current, cfg1, cfg2, c=1,
                        c1=0.5, c2=0.5, velocities=0):
    vs = velocities * c + (self.get_value(cfg1) - self.get_value(
      current)) * c1 * random.random() + (self.get_value(
      cfg2) - self.get_value(current)) * c2 * random.random()
    p = self.get_value(current) + vs
    p = min(self.max_value, max(p, self.min_value))
    self.set_value(current, p)
    return v

  def sv_mutate(self, dest, *args, **kwargs):
    #TODO
    pass


##################

class ManipulatorProxy(object):
  """
  wrapper around configuration manipulator and config pair
  """

  def __init__(self, manipulator, cfg):
    self.cfg = cfg
    self.manipulator = manipulator
    self.params = manipulator.parameters_dict(self.cfg)

  def keys(self):
    return self.params.keys()

  def __getitem__(self, k):
    return ParameterProxy(self.params[k], self.cfg)


class ParameterProxy(object):
  """
  wrapper aint parameter and config pair, adds config
  as first argument to all method calls to parameter
  """

  def __init__(self, param, cfg):
    self.cfg = cfg
    self.param = param

  def __getattr__(self, key):
    """equivalent of self.param.key(self.cfg, ...)"""
    member = getattr(self.param, key)

    def param_method_proxy(*args, **kwargs):
      return member(self.cfg, *args, **kwargs)

    if callable(member):
      return param_method_proxy
    else:
      # we should only hit this for key == 'name'
      return member


# Inspection Methods
def SVs(param):
  """ 
  Return a list of operator function names of given parameter 
  param: a Parameter class   
  """
  svs = []
  methods = inspect.getmembers(param, inspect.ismethod)
  for m in methods:
    name, obj = m
    if isSV(name):
      svs.append(name)
  return svs


def isSV(name):
  """ Tells whether a method is an operator by method name """
  return ('sv_' == name[:3])


def allSVs():
  """ Return a dictionary mapping from parameter names to lists of operator function names """
  svs = {}
  for p in all_params():
    name, obj = p
    svs[name] = SVs(obj)
  return svs


def all_params():
  params = inspect.getmembers(sys.modules[__name__], lambda x: inspect.isclass(
    x) and x.__module__ == __name__ and issubclass(x, Parameter))
  return params
