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
      dst_params[k].op4_set_linear(cfg_a, cfg_b, cfg_c, a, b, c)
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

    #TODO sub parameters should be recursed on
    # not currently an issue since no doubly-nested sub-parameters
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
      p.op1_randomize(cfg)
    return cfg

  def parameters(self, config):
    """return a list of Parameter objects"""
    if type(config) is not self.config_type:
      log.error("wrong type, expected %s got %s",
                str(self.config_type),
                str(type(config)))
      raise TypeError()
    return self.params

  def parameters_to_json(self):
    """
    output information about the parameters in this manipulator in json format:
    [ConfigurationManipulator,{pinfo:count,pinfo:count ...}]
    where pinfo has a similar form to describe the parameter's sub-parameters:
    [param_name,{pinfo:count,pinfo:count ...}]
    """
    def param_info_to_json(param, sub_parameters):
      """
      recursively output information about a parameter and its subparameters in a json format:

      [parameter_name, {subparam_info:count,subparam_info:count,...}]
      or if no subparams
      [parameter_name,{}]

      where subparam_info are sorted alphabetically. Note we can't directly use json since
      sets/dictionaries aren't always ordered by key
      """
      sub_parameter_counts = {}
      # build the string
      if isinstance(param, str):
        param_name = param
      else:
        param_name = param.__class__.__name__
      out = ['[', param_name, ',{']

      if len(sub_parameters) > 0:
        # count sub params
        for sp in sub_parameters:
          spout = param_info_to_json(sp, sp.sub_parameters())
          sub_parameter_counts[spout] = sub_parameter_counts.get(spout, 0) + 1
        # add the count map in sorted order
        for sp in sorted(sub_parameter_counts):
          out.append(sp)
          out.append(':')
          out.append(str(sub_parameter_counts[sp]))
          out.append(',')
        out.pop() # remove trailing comma

      out.append('}]')
      return ''.join(out)

    # filter out subparameters to avoid double counting
    params = [p for p in self.params if p.parent is self]
    return param_info_to_json(self, params)

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
    arg_map: python dict that maps string parameter name to class method
    arguments
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

    default implementation just has op1_randomize as only operation
    """
    return [self.op1_randomize]

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
  def op1_randomize(self, cfg):
    """
    Set this parameter's value in a configuration to a random value

    :param config: the configuration to be changed
    """
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
  def op4_set_linear(self, cfg, cfg_a, cfg_b, cfg_c, a, b, c):
    """
    Sets the parameter value in a configuration to a linear combination of 3
    other configurations: :math:`a*cfg_a + b*cfg_b + c*cfg_c`

    :param cfg: the configuration to be changed
    :param cfg_a: a parent configuration
    :param cfg_b: a parent configuration
    :param cfg_c: a parent configuration
    :param a: weight for cfg_a
    :param b: weight for cfg_b
    :param c: weight for cfg_c
    """
    pass

  def search_space_size(self):
    return 1

  def op1_nop(self, cfg):
    """
    The 'null' operator. Does nothing.

    :param cfg: the configuration to be changed
    """
    pass

  # Stochastic variators
  def op3_swarm(self, cfg, cfg1, cfg2, c, c1, c2, *args, **kwargs):
    """
    Stochastically 'move' the parameter value in a configuration towards those
    in two parent configurations. This is done by calling :py:meth:`opn_stochastic_mix`

    :param cfg: the configuration to be changed
    :param cfg1: a parent configuration
    :param cfg2: a parent configuration
    :param c: weight of original configuration
    :param c1: weight for cfg1
    :param c2: weight for cfg2
    """
    # default to probabilistic treatment
    self.opn_stochastic_mix(cfg, [cfg, cfg1, cfg2], [c, c1, c2])

  def opn_stochastic_mix(self, cfg, cfgs, ratio, *args, **kwargs):
    """
    Stochastically recombine a list of parent values into a single result.

    This randomly copies a value from a list of parents configurations according
    to a list of weights.

    :param cfg: the configuration to be changed
    :param cfgs: a list of parent configurations
    :param ratio: a list of floats representing the weight of each configuration
     in cfgs

    """
    assert len(cfgs) == len(ratio)
    r = random.random()
    c = numpy.array(ratio, dtype=float) / sum(ratio)
    for i in range(len(c)):
      if r < sum(c[:i + 1]):
        self.copy_value(cfg, cfgs[i])
        break


class PrimitiveParameter(Parameter):
  """
  An abstract interface implemented by parameters that represent a single
  dimension in a cartesian space in a legal range
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
    assert 0.0 <= unit_value <= 1.0
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

  def op1_normal_mutation(self, cfg, sigma=0.1, *args, **kwargs):
    """
    apply normally distributed noise to this parameter's value in a
    configuration

    :param cfg: The configuration to be changed
    :param sigma: the std. deviation of the normally distributed noise on a unit
     scale
    """
    v = self.get_unit_value(cfg)
    v += random.normalvariate(0.0, sigma)
    # handle boundary cases by reflecting off the edge
    if v < 0.0:
      v *= -1.0
    if v > 1.0:
      v = 1.0 - (v % 1)
    self.set_unit_value(cfg, v)

  def op4_set_linear(self, cfg, cfg_a, cfg_b, cfg_c, a, b, c):
    """
    set the parameter value in a configuration to a linear combination of 3
    other configurations: :math:`a*cfg_a + b*cfg_b + c*cfg_c`

    :param cfg: The configuration to be changed
    :param cfg_a: a parent configuration
    :param cfg_b: a parent configuration
    :param cfg_c: a parent configuration
    :param a: weight for cfg_a
    :param b: weight for cfg_b
    :param c: weight for cfg_c
    """
    va = self.get_unit_value(cfg_a)
    vb = self.get_unit_value(cfg_b)
    vc = self.get_unit_value(cfg_c)
    v = a * va + b * vb + c * vc
    v = max(0.0, min(v, 1.0))

    self.set_unit_value(cfg, v)

  def manipulators(self, config):
    """
    a list of manipulator functions to change this value in the config
    manipulators must be functions that take a config and change it in place

    for primitive params default implementation is uniform random and normal
    """
    return [self.op1_randomize, self.op1_normal_mutation]

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
  """
  A parameter representing a number with a minimum and maximum value
  """
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

  def op1_randomize(self, config):
    """
    Set this parameter's value in a configuration to a random value in its legal
     range

    :param config: the configuration to be changed
    """
    if self.is_integer_type():
      self.set_value(config, random.randint(*self.legal_range(config)))
    else:
      self.set_value(config, random.uniform(*self.legal_range(config)))

  def op1_scale(self, cfg, k):
    """
    Scale this parameter's value in a configuration by a constant factor

    :param cfg: the configuration to be changed
    :param k: the constant factor to scale the parameter value by
    """
    v = self.get_value(cfg) * k
    v = max(self.min_value, min(self.max_value, v))
    self.set_value(cfg, v)

  def op3_difference(self, cfg, cfg1, cfg2):
    """
    Set this parameter's value in a configuration to the difference between this
    parameter's values in 2 other configs (cfg2 - cfg1)

    :param cfg: the configuration to be changed
    :param cfg1: The configuration whose parameter value is being subtracted
    :param cfg2: The configuration whose parameter value is subtracted from
    """
    v = self.get_value(cfg2) - self.get_value(cfg1)
    v = max(self.min_value, min(self.max_value, v))
    self.set_value(cfg, v)

  def opn_sum(self, cfg, *cfgs):
    """
    Set this parameter's value in a configuration to the sum of it's values in a
     list of configurations

    :param cfg: the configuration to be changed
    :param cfgs: a list of configurations to sum
    """
    v = sum([self.get_value(c) for c in cfgs])
    v = max(self.min_value, min(self.max_value, v))
    self.set_value(cfg, v)

  def search_space_size(self):
    if self.value_type is float:
      return 2 ** 32
    else:
      return self.max_value - self.min_value + 1  # inclusive range


class IntegerParameter(NumericParameter):
  """
  A parameter representing an integer value in a legal range
  """
  def __init__(self, name, min_value, max_value, **kwargs):
    """min/max are inclusive"""
    kwargs['value_type'] = int
    super(IntegerParameter, self).__init__(name, min_value, max_value, **kwargs)

  def op3_swarm(self, cfg, cfg1, cfg2, c=1, c1=0.5,
                c2=0.5, velocity=0, sigma=0.2, *args, **kwargs):
    """
    Simulates a single update step in particle swarm optimization by updating
    the current position and returning a new velocity.

    The new velocity is given by

    .. math:: c*velocity + r1*c1*(cfg1-cfg) + r2*c2*(cfg2-cfg)

    where r1 and r2 are random values between 0 and 1.

    The new current position is the new velocity with gaussian noise added.

    :param cfg: the configuration to be changed. Represents the current position
    :param cfg1: a configuration to shift towards. Should be the local best
     position
    :param cfg2: a configuration to shift towards. Should be the global best
     position
    :param c: the weight of the current velocity
    :param c1: weight of cfg1
    :param c2: weight of cfg2
    :param velocity: the old velocity
    :param sigma: standard deviation of the gaussian noise, on a unit-scale
    :return: the new velocity, a float

    """
    vmin, vmax = self.legal_range(cfg)
    k = vmax - vmin
    # calculate the new velocity
    v = velocity * c + (self.get_value(cfg1) - self.get_value(
        cfg)) * c1 * random.random() + (self.get_value(
        cfg2) - self.get_value(cfg)) * c2 * random.random()
    # Map velocity to continuous space with sigmoid
    s = k / (1 + numpy.exp(-v)) + vmin
    # Add Gaussian noise
    p = random.gauss(s, sigma * k)
    # Discretize and bound
    p = int(min(vmax, max(round(p), vmin)))
    self.set_value(cfg, p)
    return v


class FloatParameter(NumericParameter):
  def __init__(self, name, min_value, max_value, **kwargs):
    """min/max are inclusive"""
    kwargs['value_type'] = float
    super(FloatParameter, self).__init__(name, min_value, max_value, **kwargs)

  def op3_swarm(self, cfg, cfg1, cfg2, c=1, c1=0.5,
                c2=0.5, velocity=0, *args, **kwargs):
    """

    Simulates a single update step in particle swarm optimization by updating
    the current position and returning a new velocity.

    The new velocity is given by

    .. math:: c*velocity + r1*c1*(cfg1-cfg) + r2*c2*(cfg2-cfg)

    where r1 and r2 are random values between 0 and 1

    The new current position is the old current position offset by the new
    velocity:

    :param cfg: the configuration to be changed. Represents the current position
    :param cfg1: a configuration to shift towards. Should be the local best
     position
    :param cfg2: a configuration to shift towards. Should be the global best
     position
    :param c: the weight of the current velocity
    :param c1: weight of cfg1
    :param c2: weight of cfg2
    :param velocity: the old velocity
    :return: the new velocity, a float

    """
    vmin, vmax = self.legal_range(cfg)
    v = velocity * c + (self.get_value(cfg1) - self.get_value(
        cfg)) * c1 * random.random() + (self.get_value(
        cfg2) - self.get_value(cfg)) * c2 * random.random()
    p = self.get_value(cfg) + v
    p = min(vmax, max(p, vmin))
    self.set_value(cfg, p)
    return v


class ScaledNumericParameter(NumericParameter):
  """
  A Parameter that is stored in configurations normally, but has a scaled
  value when accessed using 'get_value'.
  Because search techniques interact with Parameters through get_value, these
  parameters are searched on a different scale (e.g. log scale).
  """

  @abc.abstractmethod
  def _scale(self, v):
    """
    called on a value when getting it from it's configuration. Transforms the
    actual value to the scale it is searched on
    """
    return v

  @abc.abstractmethod
  def _unscale(self, v):
    """
    called on a value when storing it. Transforms a value from it's search scale
    to it's actual value
    """
    return v

  def set_value(self, config, value):
    NumericParameter.set_value(self, config, self._unscale(value))

  def get_value(self, config):
    return self._scale(NumericParameter.get_value(self, config))

  def legal_range(self, config):
    return map(self._scale, NumericParameter.legal_range(self, config))


class LogIntegerParameter(ScaledNumericParameter, FloatParameter):
  """
  an integer value that is searched on a log scale, but stored without scaling
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
  a float parameter that is searched on a log scale, but stored without scaling
  """

  def _scale(self, v):
    return math.log(v + 1.0 - self.min_value, 2.0)

  def _unscale(self, v):
    v = 2.0 ** v - 1.0 + self.min_value
    return v


class PowerOfTwoParameter(ScaledNumericParameter, IntegerParameter):
  """
  An integer power of two, with a min and max value. Searched by the exponent
  """

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


##################

class ComplexParameter(Parameter):
  """
  A non-cartesian parameter that can't be manipulated directly, but has a set
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

  def op4_set_linear(self, cfg, cfg_a, cfg_b, cfg_c, a, b, c):
    """
    set this value to :math:`a*cfg_a + b*cfg_b + c*cfg_c`

    this operation is not possible in general with complex parameters but
    we make an attempt to "fake" it for common use cases

    basically a call to randomize unless after normalization,
    a = 1.0, b == -c, and cfg_b == cfg_c, in which case nothing is done

    :param cfg: the configuration to be changed
    :param cfg_a: a parent configuration
    :param cfg_b: a parent configuration
    :param cfg_c: a parent configuration
    :param a: weight for cfg_a
    :param b: weight for cfg_b
    :param c: weight for cfg_c
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
      self.copy_value(cfg_a, cfg)
      self.add_difference(cfg, b, cfg_b, cfg_c)  # TODO inline this logic?
    else:
      # TODO: should handle more cases
      self.op1_randomize(cfg)

  def add_difference(self, cfg_dst, scale, cfg_b, cfg_c):
    """
    add the difference cfg_b-cfg_c to cfg_dst

    this is the key operation used in differential evolution
    and some simplex techniques

    this operation is not possible in general with complex parameters but
    we make an attempt to "fake" it
    """
    if not self.same_value(cfg_b, cfg_c):
      self.op1_randomize(cfg_dst)

  @abc.abstractmethod
  def op1_randomize(self, config):
    """
    randomize this value without taking into account the current position
    :param config: the configuration to be changed
    """
    pass

  @abc.abstractmethod
  def seed_value(self):
    """some legal value of this parameter (for creating initial configs)"""
    return


class BooleanParameter(ComplexParameter):
  def manipulators(self, config):
    return [self.op1_flip]

  def get_value(self, config):
    return self._get(config)

  def set_value(self, config, value):
    self._set(config, value)

  def op1_randomize(self, config):
    """
    Set this parameter's value in a configuration randomly

    :param config: the configuration to be changed
    """
    self._set(config, self.seed_value())

  def seed_value(self):
    return random.choice((True, False))

  def op1_flip(self, config):
    """
    Flip this parameter's value in a configuration

    :param config: the configuration to be changed
    """
    self._set(config, not self._get(config))

  def search_space_size(self):
    return 2

  def op3_swarm(self, cfg, cfg1, cfg2, c=1, c1=0.5,
                c2=0.5, velocity=0, *args, **kwargs):
    """
    Simulates a single update step in particle swarm optimization by updating
    the current position and returning a new velocity.

    The new velocity is given by

    .. math:: c*velocity + r1*c1*(cfg1-cfg) + r2*c2*(cfg2-cfg)

    where r1 and r2 are random values between 0 and 1

    The new current position is randomly chosen based on the new velocity

    :param cfg: the configuration to be changed. Represents the current position
    :param cfg1: a configuration to shift towards. Should be the local best position
    :param cfg2: a configuration to shift towards. Should be the global best position
    :param c: the weight of the current velocity
    :param c1: weight of cfg1
    :param c2: weight of cfg2
    :param velocity: the old velocity
    :param args:
    :param kwargs:
    :return: the new velocity, a float

    """
    v = velocity * c + (self.get_value(cfg1) - self.get_value(
        cfg)) * c1 * random.random() + (self.get_value(
        cfg2) - self.get_value(cfg)) * c2 * random.random()
    # Map velocity to continuous space with sigmoid
    s = 1 / (1 + numpy.exp(-v))
    # Decide position randomly
    p = (s - random.random()) > 0
    self.set_value(cfg, p)
    return v


class SwitchParameter(ComplexParameter):
  """
  A parameter representing an unordered collection of options with no implied
  correlation between the choices. The choices are range(option_count)
  """

  def __init__(self, name, option_count):
    self.option_count = option_count
    super(SwitchParameter, self).__init__(name)

  def op1_randomize(self, config):
    """
    Set this parameter's value in a configuration to a random value

    :param config: the configuration to be changed
    """
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

  def op1_randomize(self, config):
    """
    Set this parameter's value in a configuration to a random value

    :param config: the configuration to be changed
    """
    self._set(config, random.choice(self.options))

  def seed_value(self):
    return random.choice(self.options)

  def search_space_size(self):
    return max(1, len(self.options))


class PermutationParameter(ComplexParameter):
  """
  A parameter representing a permutation (or ordering) as a list of items
  """
  def __init__(self, name, items):
    super(PermutationParameter, self).__init__(name)
    self._items = list(items)
    self.size = len(items)

  def op1_randomize(self, config):
    """
    Set this parameter's value in a configuration to a random value

    :param config: the configuration to be changed
    """
    random.shuffle(self._get(config))
    self.normalize(config)

  def op1_small_random_change(self, config, p=0.25):
    """
    Iterates through the list and probabilistically swaps each element with the
    next element

    :param p: probability of swapping an element with the next element
    :param config: the configuration to be changed
    """
    cfg_item = self._get(config)
    for i in xrange(1, len(cfg_item)):
      if random.random() < p:
        # swap
        cfg_item[i - 1], cfg_item[i] = cfg_item[i], cfg_item[i - 1]
    self.normalize(config)

  def seed_value(self):
    return list(self._items)  # copy

  def manipulators(self, config):
    return [self.op1_randomize, self.op1_small_random_change]

  def get_value(self, config):
    return self._get(config)

  def set_value(self, config, value):
    self._set(config, value)

  def search_space_size(self):
    return math.factorial(max(1, len(self._items)))

  def op3_cross(self, cfg, cfg1, cfg2, xchoice='op3_cross_OX1', strength=0.3,
                *args, **kwargs):
    """
    Calls the crossover operator specified by xchoice
    Passes argument d = strength*(size of the permutation)

    :param cfg: the configuration to be changed
    :param cfg1: a parent configuration
    :param cfg2: a parent configuration
    :param xchoice: string specifying which crossover operator to use (should start with op3_cross prefix)
    :param strength: the strength of the crossover
    """
    dd = int(round(self.size * strength))
    if dd < 1:
      log.warning('Crossover length too small. Cannot create new solution.')
    if dd >= self.size:
      log.warning('Crossover length too big. Cannot create new solution.')
    getattr(self, xchoice)(cfg, cfg1, cfg2, d=dd, *args, **kwargs)

  def op3_swarm(self, cfg, cfg1, cfg2, xchoice='op3_cross_OX1', c=0.5,
                c1=0.5, c2=0.5, strength=0.3, velocity=0, *args, **kwargs):
    """
    Replacement for particle swarm optimization iterative step for permutations.
    Given a target cfg and 2 parent cfgs, probabilistically performs an
    op3_cross with one of the 2 parents.

    :param cfg: the configuration to be changed. Represents the current position
    :param cfg1: a configuration to shift towards. Should be the local best
     position
    :param cfg2: a configuration to shift towards. Should be the global best
     position
    :param xchoice: which crossover operator should be used
    :param c: the probability of not performing a crossover
    :param c1: the probability of performing a crossover with cfg1 (if a
     crossover is performed)
    :param c2: unused
    :param strength: the strength of the crossover
    :param velocity: the old velocity - unused
    """
    if random.uniform(0, 1) > c:
      if random.uniform(0, 1) < c1:
        # Select crossover operator
        self.op3_cross(cfg, cfg, cfg1, xchoice, strength)
      else:
        self.op3_cross(cfg, cfg, cfg2, xchoice, strength)

  # swap-based operators
  def op2_random_swap(self, cfg, cfg1, *args, **kwargs):
    """
    Swap a random pair of items in cfg1 and save the result into cfg

    :param cfg: the configuration to be changed
    :param cfg1: the configuration whose PermutationParameter's elements are
     swapped and copied into cfg
    """
    p = self.get_value(cfg1)[:]
    r = random.randint(0, len(p) - 1)
    s = random.randint(0, len(p) - 1)
    v1 = p[r]
    v2 = p[s]
    p[r] = v2
    p[s] = v1
    self.set_value(cfg, p)

  def op2_random_invert(self, cfg, cfg1, strength=0.3, *args, **kwargs):
    """
    Reverse the ordering of a random subsection of size d in cfg1 and save the
    result in cfg where d = strength*total-size

    :param cfg: the configuration to be changed
    :param cfg1: the configuration whose PermutationParameter is inverted
    :param strength: the size of the reversed subsection as a fraction of the
     total size
    """
    p = self.get_value(cfg1)[:]
    d = int(round(len(p) * strength))
    r = random.randint(0, len(p) - d)
    subpath = p[r:r + d][:]
    subpath.reverse()
    p[r:r + d] = subpath
    self.set_value(cfg, p)

  # Crossover operators
  def op3_cross_PX(self, cfg, cfg1, cfg2, d=0):
    """
    Partition crossover (Whitley 2009?)

    Chooses a random cut point and reorders elements in cfg1 up to the cut point
    according to their order in cfg2.

    Saves the result in cfg

    :param cfg: the configuration to be changed
    :param cfg1: the first parent configuration. The "base" configuration
    :param cfg2: the second parent configuration. Is "crossed into" cfg1
    :param d: unused
    """
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    c1 = random.randint(2, len(p1))
    self.set_value(cfg, sorted(p1[:c1], key=lambda x: p2.index(x)) + p1[c1:])

  def op3_cross_PMX(self, cfg, cfg1, cfg2, d=0):
    """
    Partially-mapped crossover Goldberg & Lingle (1985)

    Replaces a random section of cfg1 with the corresponding section in cfg2.
    Displaced elements in cfg1 are moved to the old position of the elements
    displacing them

    :param cfg: the configuration to be changed
    :param cfg1: the first parent configuration. The "base" configuration
    :param cfg2: the second parent configuration. Is "crossed into" cfg1
    :param d: the size of the crossover
    """
    if d == 0:
      d = max(1, int(round(self.size * 0.3))) # default to 1/3 of permutation size
    p1 = self.get_value(cfg1)[:]
    p2 = self.get_value(cfg2)[:]

    r = random.randint(0, len(p1) - d)

    c1 = p1[r:r + d]
    c2 = p2[r:r + d]

    # get new permutation by crossing over a section of p2 onto p1
    pnew = self.get_value(cfg1)[:]
    pnew[r:r + d] = c2
    # fix conflicts by taking displaced elements in crossed over section
    # displaced = (elements x in c1 where x does not have corresponding value in c2)
    # and putting them where the value that displaced them was

    #candidates for displacement
    candidate_indices = set(range(r) + range(r+d, len(p1)))
    # Check through displaced elements to find values to swap conflicts to
    while c1 != []:
      n = c1[0]
      #try to match up a value in c1 to the equivalent value in c2
      while c2[0] in c1:
        if n == c2[0]:
          # already match up
          break
        # find position idx of c2[0] in c1
        link_idx = c1.index(c2[0])
        # get value of c2 at idx
        link = c2[link_idx]
        # remove c2[idx] and c1[idx] since they match up when we swap c2[0] with c2[idx] (this avoids an infinite loop)
        del c2[link_idx]
        del c1[link_idx]
        # swap new value into c2[0]
        c2[0] = link

      if n != c2[0]:
        # first check if we can swap in the crossed over section still
        if n in c2:
          c2[c2.index(n)] = c2[0]
        else:
          # assign first instance of c2[0] outside of the crossed over section in pnew to c1[0]
          for idx in candidate_indices:
            if pnew[idx] == c2[0]:
              pnew[idx] = c1[0]
              candidate_indices.remove(idx) # make sure we don't override this value now
              break
      # remove first elements
      del c1[0]
      del c2[0]
    self.set_value(cfg, pnew)

  def op3_cross_CX(self, cfg, cfg1, cfg2, d=0):
    """
    Implementation of a cyclic crossover.

    Repeatedly replaces elements of cfg1 with the element at the same index in
    cfg2. This is done until a cycle is reached and cfg1 is valid again. The
    initial replacement is random.

    Saves the result in cfg.

    :param cfg: the configuration to be changed
    :param cfg1: the first parent configuration. The "base" configuration
    :param cfg2: the second parent configuration. Is "crossed into" cfg1
    :param d: unused
    """
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    p = p1[:]

    s = random.randint(0, len(p1) - 1)
    i = s
    indices = set()

    while len(indices) < len(p1): # should never exceed this
      indices.add(i)
      val = p1[i]
      i = p2.index(val)
      # deal with duplicate values
      while i in indices:
        if i == s:
          break
        i = p2[i+1:].index(val) + i + 1
      if i == s:
        break

    for j in indices:
      p[j] = p2[j]

    self.set_value(cfg, p)

  def op3_cross_OX1(self, cfg, cfg1, cfg2, d=0):
    """
    Ordered Crossover (Davis 1985)

    Exchanges a subpath from cfg2 into cfg1 while maintaining the order of the
    remaining elements in cfg1.

    Saves the result in cfg.

    :param cfg: the configuration to be changed
    :param cfg1: the first parent configuration. The "base" configuration
    :param cfg2: the second parent configuration. Is "crossed into" cfg1
    :param d: size of the exchanged subpath
    """
    if d == 0:
      d = max(1, int(round(self.size * 0.3))) # default to 1/3 of permutation size
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    c1 = p1[:]
    c2 = p2[:]
    # Randomly find cut points
    r = random.randint(0, len(
        p1) - d)  # Todo: treat path as circle i.e. allow cross-boundary cuts
    [c1.remove(i) for i in p2[r:int(r + d)]]
    self.set_value(cfg, c1[:r] + p2[r:r + d] + c1[r:])

  def op3_cross_OX3(self, cfg, cfg1, cfg2, d=0):
    """
    Ordered crossover variation 3 (Deep 2010)

    Same as op3_cross_OX1, except the parents have different cut points for
    their subpaths

    :param cfg: the configuration to be changed
    :param cfg1: the first parent configuration. The "base" configuration
    :param cfg2: the second parent configuration. Is "crossed into" cfg1
    :param d: size of the exchanged subpath
    """
    if d == 0:
      d = max(1, int(round(self.size * 0.3))) # default to 1/3 of permutation size
    p1 = self.get_value(cfg1)
    p2 = self.get_value(cfg2)
    c1 = p1[:]
    c2 = p2[:]
    # Randomly find cut points
    # Todo: treat path as circle i.e. allow cross-boundary cuts
    r1 = random.randint(0, len(p1) - d)
    r2 = random.randint(0, len(p1) - d)
    [c1.remove(i) for i in p2[r2:r2 + d]]
    self.set_value(cfg, c1[:r1] + p2[r2:r2 + d] + c1[r1:])

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

  def op1_randomize(self, config):
    random.choice(self.sub_parameters()).op1_randomize(config)

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


class ParameterArray(ComplexParameter):
  """
  Represents an array of Parameters
  """
  def __init__(self, name, count, element_type, *args, **kwargs):
    super(ParameterArray, self).__init__(name)
    self.count = count

    self.sub_params = [
        element_type('{0}/{1}'.format(name, i), *args[i], **kwargs[i])
        for i in xrange(count)]

  def sub_parameters(self):
    return self.sub_params

  def seed_value(self):
    return [p.seed_value() for p in self.sub_params]

  def op1_randomize(self, config):
    """
    randomly selects a sub-parameter and randomizes it

    :param config: the configuration to be changed
    """
    random.choice(self.sub_parameters()).op1_randomize(config)


class BooleanParameterArray(ParameterArray):
  """
  Represents an array of BooleanParameters - currently unimplimented
  """
  def __init__(self, name, count):
    super(BooleanParameterArray, self).__init__(name, count, BooleanParameter)

  def op3_swarm(self, cfg, cfg1, cfg2, *args, **kwargs):
    # TODO
    pass

  def op3_cross(self, cfg, cfg1, cfg2, *args, **kwargs):
    # TODO
    pass


class IntegerParameterArray(ParameterArray):
  """
  Represents an array of IntegerParameters - currently unimplemented
  """
  def __init__(self, name, min_values, max_values):
    assert len(min_values) == len(max_values)
    super(IntegerParameterArray, self).__init__(name, len(min_values),
                                                IntegerParameter,
                                                min_value=min_values,
                                                max_value=max_values)

  def op3_swarm(self, cfg, cfg1, cfg2, *args, **kwargs):
    # TODO
    pass

  def op3_cross(self, cfg, cfg1, cfg2, *args, **kwargs):
    # TODO
    pass


class Array(ComplexParameter):
  """
  An interface for parameters representing an array of values.
  """
  # TODO: constraints? (upper & lower bound etc)
  def __init__(self, name, size):
    super(Array, self).__init__(name)
    self.size = size

  def op3_cross(self, cfg, cfg1, cfg2, strength=0.3, *args, **kwargs):
    """
    Crosses two arrays by replacing a random subsection of cfg1 with the
    corresponding subsection of cfg2.The size of the chunk is a fixed fraction
    of the total length, given by the strength

    Behaves like a specialized 2-point crossover, where the first cut point is
    random and the second cut is a set distance after.

    :param cfg: the configuration to be changed
    :param cfg1: the configuration being inserted into
    :param cfg2: the configuration being inserted
    :param strength: the size of the crossover, as a fraction of total array
     length
    """
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
    self.set_value(cfg, p)

  def op3_swarm(self, cfg, cfg1, cfg2, c=1, c1=0.5,
                c2=0.5, velocity=0, strength=0.3, *args, **kwargs):
    """
    Replacement for a particle swarm optimization iterative step for arrays.
    Given a target cfg and 2 parent cfgs, probabilistically performs an
    :py:meth:`op3_cross` with one of the 2 parents.

    :param cfg: the configuration to be changed. Represents the cfg position
    :param cfg1: a configuration to shift towards. Should be the local best
     position
    :param cfg2: a configuration to shift towards. Should be the global best
     position
    :param c: the probability of not performing a crossover
    :param c1: the probability of performing a crossover with cfg1 (if a
     crossover is performed)
    :param c2: unused
    :param velocity: the old velocity - unused
    :param strength: the strength of the crossover
    """
    if random.uniform(0, 1) > c:
      if random.uniform(0, 1) < c1:
        # Select crossover operator
        self.op3_cross(cfg, cfg, cfg1, strength)
      else:
        self.op3_cross(cfg, cfg, cfg2, strength)

  def get_value(self, config):
    return self._get(config)

  def set_value(self, config, value):
    self._set(config, value)


class BooleanArray(Array):
  """
  Represents an array of boolean values which are either 0 or 1
  """
  def op3_swarm_parallel(self, cfg, cfg1, cfg2, c=1,
                         c1=0.5, c2=0.5, velocities=0):
    """
    Simulates a single particle swarm optimization step for each element in the
    array by updating each position and returning an array of new velocities.

    The new velocities are given by

    .. math:: c*velocity + r1*c1*(cfg1-cfg) + r2*c2*(cfg2-cfg)

    where r1 and r2 are random values between 0 and 1. In each iteration, r1 and
    r2 are constant across array elements

    The new cfg positions are randomly chosen based on the new velocities

    :param cfg: the configuration to be changed. This represents the current
     position
    :param cfg1: a configuration to shift towards. Should be the local best
     position
    :param cfg2: a configuration to shift towards. Should be the global best
     position
    :param c: the weight of the current velocities
    :param c1: weight of cfg1
    :param c2: weight of cfg2
    :param velocities: the current velocities
    :return: a numpy array of new velocities
    """
    vs = velocities * c + (self.get_value(cfg1) - self.get_value(
        cfg)) * c1 * random.random() + (self.get_value(
            cfg2) - self.get_value(cfg)) * c2 * random.random()
    # Map velocity to continuous space with sigmoid
    ss = 1 / (1 + numpy.exp(-vs))
    # Decide position randomly
    ps = (ss - numpy.random.rand(1, self.size)) > 0
    self.set_value(cfg, ps)
    return vs

  def op1_randomize(self, config):
    """
    Set this parameter's value in a configuration randomly

    :param config: the configuration to be changed
    """
    value = numpy.random.rand(1, self.size) > 0.5
    self._set(config, value)

  def seed_value(self):
    return numpy.random.rand(1, self.size) > 0.5


class FloatArray(Array):
  """
  Represents an array of float values
  """
  def __init__(self, name, size, fmax, fmin):
    super(FloatArray, self).__init__(name, size)
    self.fmax = fmax
    self.fmin = fmin

  def op1_randomize(self, config):
    """
    Set this parameter's value in a configuration randomly

    :param config: the configuration to be changed
    """
    value = numpy.random.rand(1, self.size) * (
        self.fmax - self.fmin) + self.fmin
    self._set(config, value)

  def seed_value(self):
    value = numpy.random.rand(1, self.size) * (
        self.fmax - self.fmin) + self.fmin
    return value

  def op3_swarm_parallel(self, cfg, cfg1, cfg2, c=1,
                         c1=0.5, c2=0.5, velocities=0):
    """
    Simulates a single particle swarm optimization step for each element in the
    array by updating the each position and returning an array of new velocities

    The new velocity is given by

    .. math:: c*velocity + r1*c1*(cfg1-cfg) + r2*c2*(cfg2-cfg)

    where r1 and r2 are random values between 0 and 1. In each iteration, r1 and
    r2 are constant across array elements

    The new cfg positions are randomly chosen based on the new velocities

    :param cfg: the configuration to be changed. This represents the current
     position
    :param cfg1: a configuration to shift towards. Should be the local best
     position
    :param cfg2: a configuration to shift towards. Should be the global best
     position
    :param c: the weight of the cfg velocities
    :param c1: weight of cfg1
    :param c2: weight of cfg2
    :param velocities: the cfg velocities
    :return: a numpy array of new velocities
    """
    vs = velocities * c + (self.get_value(cfg1) - self.get_value(
        cfg)) * c1 * random.random() + (self.get_value(
        cfg2) - self.get_value(cfg)) * c2 * random.random()
    p = self.get_value(cfg) + vs
    p[p > self.fmax] = self.fmax
    p[p < self.fmin] = self.fmin
    self.set_value(cfg, p)
    return vs


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
def operators(param, num_parents):
  """
  Return a list of operators for the given parameter that take the specified
  number of input configurations

  :param param: a Parameter class
  :param num_parents: a String specifying number of inputs required by the operator.
    should be one of '1', '2', '3', '4', or 'n'
  """
  ops = []
  methods = inspect.getmembers(param, inspect.ismethod)
  for m in methods:
    name, obj = m
    if is_operator(name, num_parents):
      ops.append(name)
  return ops

def composable_operators(param, min_num_parents):
  """
  Return a list of operators for the given parameter that can be programatically composed
  with a composable technique generating min_num_parents.

  Programatically composable operators have no non-cfg arguments

  :param param: a Parameter class
  :param min_num_parents: the minimum number of parents passed to the operator
  """
  if min_num_parents < 1:
    return []

  allowed_num_parents = ['n']
  for i in range(1,5):
    if i > min_num_parents:
      break
    allowed_num_parents.append(str(i))

  ops = []
  methods = inspect.getmembers(param, inspect.ismethod)
  for m in methods:
    name, obj = m
    argspec = inspect.getargspec(obj)
    numargs = len(argspec.args) - (len(argspec.defaults) if argspec.defaults else 0)
    for num_parents in allowed_num_parents:
      if is_operator(name, num_parents):
        if num_parents == 'n':
          if numargs == 3: # self, cfg, cfgs
            ops.append(name)
        else:
          if numargs == (1 + int(num_parents)):
            ops.append(name)
        break
  return ops


def is_operator(name, num_parents):
  """
  Tells whether a method is an operator taking in the specified number of inputs
  from the method name

  :param name: the method name
  :param num_parents: a String specifying number of inputs required by the operator.
    should be one of '1', '2', '3', '4', or 'n'
  """
  return ('op' + num_parents + '_') == name[:4]

def all_operators():
  """
  Return a dictionary mapping from parameter names to lists of operator function
  names
  """
  ops = {}
  for p in all_params():
    name, obj = p
    all_ops = []
    for num in ['1', '2', '3', '4', 'n']:
      all_ops += operators(obj, num)
    ops[name] = all_ops
  return ops

def all_params():
  params = inspect.getmembers(sys.modules[__name__], lambda x: inspect.isclass(
    x) and x.__module__ == __name__ and issubclass(x, Parameter))
  return params

