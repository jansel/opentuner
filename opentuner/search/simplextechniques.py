import abc
import copy
import random
import logging
from collections import defaultdict
import fn
from fn import _
from fn.iters import map, filter, repeat
from opentuner.resultsdb.models import *
from .technique import SequentialSearchTechnique
from .manipulator import Parameter

log = logging.getLogger(__name__)


class SimplexTechnique(SequentialSearchTechnique):
  '''
  Base class with utility functions common
  to simplex type methods
  '''

  def __init__(self, *args, **kwargs):
    self.simplex_points = []
    self.last_simplex_points = None
    self.centroid = None
    super(SimplexTechnique, self).__init__(*args, **kwargs)

  def calculate_centroid(self):
    '''
    average of all the PrimativeParameters in self.simplex_points
    ComplexParameters are copied from self.simplex_points[0]
    '''
    sums   = defaultdict(float)
    counts = defaultdict(int)

    for config in self.simplex_points:
      cfg = config.data
      for param in self.manipulator.parameters(cfg):
        if param.is_primative():
          sums[param.name] += param.get_unit_value(cfg)
          counts[param.name] += 1

    centroid = self.manipulator.copy(self.simplex_points[0].data)
    for param in self.manipulator.parameters(centroid):
      if param.is_primative():
        param.set_unit_value(centroid,
                             sums[param.name] / float(counts[param.name]))

    return centroid

  def cfg_to_str(self, cfg):
    params = list(filter(Parameter.is_primative,
                         self.manipulator.parameters(cfg)))
    params.sort(key=_.name)
    return str(tuple(map(lambda x: x.get_unit_value(cfg), params)))

  def debug_log(self):
    for i, config in enumerate(self.simplex_points):
      log.debug("simplex_points[%d] = %s", i, self.cfg_to_str(config.data))
    if self.centroid:
      log.debug("centroid = %s", self.cfg_to_str(self.centroid))

  def linear_point(self, p1, p2, scale):
    '''
    return a point on the line passing between p1 and p2 at position scale
    such that p1 + scale*(p1 - p2)
    '''
    p3 = self.manipulator.copy(p1)
    p2_params = self.manipulator.parameters_dict(p2)
    for param1 in self.manipulator.parameters(p1):
      if param1.is_primative():
        try:
          param2 = p2_params[param1.name]
        except KeyError:
          # p2 doesn't have this param, must be a dynamic config structure
          continue

        v1 = param1.get_unit_value(p1)
        v2 = param2.get_unit_value(p2)

        v3 = v1 + scale*(v1 - v2)
        v3 = max(0.0, min(v3, 1.0))

        # we can reuse param1 here since p3 is a copy of p1
        param1.set_unit_value(p3, v3)

    return p3

  def convergence_criterea(self):
    '''True will cause the simplex method to stop'''
    if self.last_simplex_points == self.simplex_points:
      return True
    self.last_simplex_points = list(self.simplex_points)
    return False

  @abc.abstractmethod
  def initial_simplex(self):
    '''
    return a initial list of configurations
    '''
    return []


class RandomInitialSimplexMixin(object):
  '''
  start with random initial simplex
  '''
  def initial_simplex(self):
    # we implicitly assume number of parameters is fixed here, however 
    # it will work if it isn't (simplex size is undefined)
    p0 = self.manipulator.random()
    params = self.manipulator.parameters(p0)
    return [p0]+[self.manipulator.random()
                 for p in params
                 if p.is_primative()]


class NelderMead(SimplexTechnique):
  '''
  Nelder-Mead downhill simplex method.

  Based on description of method on page 82 of
  'Noisy Optimization With Evolution Strategies' by Dirk V. Arnold.

  We set alpha=2.0 by default instead of the often recommended alpha=1.0 to
  avoid a common degenerate case, where the volume of the simplex becomes zero.
  This is easiest to see with a single parameter. Let the simplex points
  be x0,x1.  Let the centroid be c=(x0+x1)/2.0 and the reflection point be:
  reflection = c + alpha*(c-x1) = (x0+x1)*(1+alpha)/2 - x1
  The problem is, if we set alpha = 1.0, then the x1's cancel out and the
  reflection point becomes just reflection=x0, which also happens to be the
  second best point, meaning we will use it.  So in a single step of the
  algorithm the simplex becomes singular.
  '''

  def __init__(self,
               alpha=2.0,
               gamma=2.0,
               beta=0.5,
               sigma=0.5,
               *args, **kwargs):
    self.alpha = alpha
    self.gamma = gamma
    self.beta  = beta
    self.sigma = sigma
    super(NelderMead, self).__init__(*args, **kwargs)

  def main_generator(self, manipulator, driver):
    objective = driver.objective
    self.manipulator = manipulator
    self.driver = driver

    # test the entire initial simplex
    self.simplex_points = list(map(driver.get_configuration,
                                   self.initial_simplex()))
    log.info("initial points")
    for p in self.simplex_points:
      self.yield_nonblocking(p)
    yield None # wait until results are ready

    while not self.convergence_criterea():
      # next steps assume this ordering
      self.simplex_points.sort(cmp=objective.compare)
      self.centroid = self.calculate_centroid()
      if log.isEnabledFor(logging.DEBUG):
        self.debug_log()

      reflection = self.reflection_point()
      yield reflection

      if objective.lt(reflection, self.simplex_points[0]):
        #expansion case
        expansion = self.expansion_point(reflection)
        yield expansion

        if objective.lt(expansion, reflection):
          log.info("using expansion point")
          self.simplex_points[-1] = expansion
        else:
          log.info("using reflection point (considered expansion)")
          self.simplex_points[-1] = reflection

      elif objective.lt(reflection, self.simplex_points[1]):
        #reflection case
        log.info("using reflection point")
        self.simplex_points[-1] = reflection
      else:
        # contraction case
        if objective.lte(reflection, self.simplex_points[-1]):
          # outside contraction
          contract_base = reflection
        else:
          # inside contraction
          contract_base = self.simplex_points[-1]

        contraction = self.contraction_point(contract_base)
        yield contraction

        if objective.lte(contraction, contract_base):
          log.info("using contraction point")
          self.simplex_points[-1] = contraction
        else:
          #reduction case
          log.info("performing shrink reduction")
          self.perform_shrink_reduction()
          for p in self.simplex_points:
            self.yield_nonblocking(p)
          yield None # wait until results are ready

  def reflection_point(self):
    '''
    reflect worst point across centroid
    '''
    return self.driver.get_configuration(
             self.linear_point(self.centroid,
                               self.simplex_points[-1].data,
                               self.alpha))

  def expansion_point(self, reflection):
    '''
    reflect worst point across centroid more (by default 2x as much)
    '''
    return self.driver.get_configuration(
             self.linear_point(self.centroid,
                               reflection.data,
                               -self.gamma))

  def contraction_point(self, contract_base):
    '''
    reflect worst point across centroid less
    '''
    return self.driver.get_configuration(
             self.linear_point(self.centroid,
                               contract_base.data,
                               -self.beta))

  def perform_shrink_reduction(self):
    '''
    shrink the simplex in size by sigma=1/2 (default), moving it closer to the
    best point
    '''
    for i in xrange(1, len(self.simplex_points)):
      self.simplex_points[i] = self.driver.get_configuration(
          self.linear_point(
            self.simplex_points[0].data,
            self.simplex_points[i].data,
            -self.sigma
        ))


class Torczon(SimplexTechnique):
  '''
  Torczon multi-directional search algorithm.

  Based on description of method on page 85 of
  'Noisy Optimization With Evolution Strategies' by Dirk V. Arnold.
  '''

  def __init__(self,
               alpha=1.0,
               gamma=2.0,
               beta=0.5,
               *args, **kwargs):
    self.alpha = alpha
    self.gamma = gamma
    self.beta  = beta
    super(Torczon, self).__init__(*args, **kwargs)

  def main_generator(self, manipulator, driver):
    objective = driver.objective
    self.manipulator = manipulator
    self.driver = driver

    # test the entire initial simplex
    self.simplex_points = list(map(driver.get_configuration,
                                   self.initial_simplex()))
    log.info("initial points")
    for p in self.simplex_points:
      self.yield_nonblocking(p)
    yield None # wait until results are ready
    self.simplex_points.sort(cmp=objective.compare)

    while not self.convergence_criterea():
      if log.isEnabledFor(logging.DEBUG):
        self.debug_log()

      reflected = self.reflected_simplex()
      yield None # wait until results are ready
      reflected.sort(cmp=objective.compare)

      # this next condition implies reflected[0] < simplex_points[0] since
      # reflected is sorted and contains simplex_points[0] (saves a db query)
      if reflected[0] is not self.simplex_points[0]:
        expanded = self.expanded_simplex()
        yield None # wait until results are ready
        expanded.sort(cmp=objective.compare)

        if objective.lt(expanded[0], reflected[0]):
          log.info("expansion performed")
          self.simplex_points = expanded
        else:
          log.info("reflection performed")
          self.simplex_points = reflected
      else:
        contracted = self.contracted_simplex()
        yield None # wait until results are ready
        contracted.sort(cmp=objective.compare)

        log.info("contraction performed")
        self.simplex_points = contracted

  def scaled_simplex(self, scale):
    '''
    assumes self.simplex_points[0] is best point and returns a new simplex
    reflected across self.simplex_points[0] by scale
    '''
    simplex = list(self.simplex_points) # shallow copy
    for i in xrange(1, len(simplex)):
      simplex[i] = self.driver.get_configuration(
          self.linear_point(simplex[0].data, simplex[i].data, scale)
        )
      self.yield_nonblocking(simplex[i])
    return simplex

  def reflected_simplex(self):  return self.scaled_simplex(self.alpha)
  def expanded_simplex(self):   return self.scaled_simplex(self.gamma)
  def contracted_simplex(self): return self.scaled_simplex(-self.beta)

class RandomNelderMead(RandomInitialSimplexMixin, NelderMead):
  pass

class RandomTorczon(RandomInitialSimplexMixin, Torczon):
  pass


