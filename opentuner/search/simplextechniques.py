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
  Nelder-Mead downhill simplex method
  '''

  def __init__(self, alpha=1.0, gamma=4.0, rho=-0.5, sigma=0.5):
    self.alpha = alpha
    self.gamma = gamma
    self.rho   = rho
    self.sigma = sigma
    self.simplex_points = None
    super(SimplexTechnique, self).__init__()

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
        expansion = self.expansion_point()
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
        contraction = self.contraction_point()
        yield contraction

        if objective.lt(contraction, self.simplex_points[-1]):
          log.info("using contraction point")
          self.simplex_points[-1] = contraction
        else:
          #reduction case
          log.info("performing reduction")
          self.perform_reduction()
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

  def expansion_point(self):
    '''
    reflect worst point across centroid more (by default 2x as much)
    '''
    return self.driver.get_configuration(
             self.linear_point(self.centroid,
                               self.simplex_points[-1].data,
                               self.gamma))

  def contraction_point(self):
    '''
    reflect worst point across centroid less
    '''
    return self.driver.get_configuration(
             self.linear_point(self.centroid,
                               self.simplex_points[-1].data,
                               self.rho))

  def perform_reduction(self):
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

  def convergence_criterea(self):
    '''True will cause the simplex method to stop'''
    return False

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

  @abc.abstractmethod
  def initial_simplex(self):
    '''
    return a initial list of configurations
    '''
    return []


class RandomSimplex(SimplexTechnique):
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








