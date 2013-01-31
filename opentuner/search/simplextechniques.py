import abc
import copy
import random
import logging
from fn import _
from fn.iters import map, filter
from opentuner.resultsdb.models import *
from technique import SearchTechnique

log = logging.getLogger(__name__)

def between(a, b, c)
  return a <= b and b <= c

class SimplexTechnique(ProceduralSearchTechnique):
  '''
  Nelder-Mead downhill simplex method
  '''
  def __init__(self, alpha=1.0, gamma=2.0, rho=-0.5, sigma=0.5):
    self.alpha = alpha
    self.gamma = gamma
    self.rho   = rho
    self.sigma = sigma
    self.simplex_points = None
    super(SimplexTechnique, self).__init__()

  def main_generator(self, manipulator, driver):
    objective = driver.objective_function
    self.manipulator = manipulator
    self.driver = driver

    # test the entire initial simplex
    self.simplex_points = self.initial_simplex(manipulator, driver)
    log.info("initial points")
    for p in self.simplex_points:
      if not driver.has_results(p):
        yield p
    while not all(map(driver.has_results, self.simplex_points)):
      yield None # wait until results are ready

    while not self.convergence_criterea():
      # next steps assume this ordering
      self.simplex_points.sort(key=objective)
      self.centroid = self.calculate_centroid()

      reflection = self.reflection_point()
      yield reflection
      while not driver.has_results(reflection):
        yield None # wait until results are ready

      if objective(reflection) < self.simplex_points[0]:
        #expansion case
        expansion = self.expansion_point()
        yield expansion
        while not driver.has_results(expansion):
          yield None # wait until results are ready

        if objective(expansion) < objective(reflection):
          log.info("using expansion point")
          self.simplex_points[-1] = expansion
        else:
          log.info("using reflection point")
          self.simplex_points[-1] = reflection

      elif objective(reflection) < self.simplex_points[1]:
        #reflection case
        log.info("using reflection point")
        self.simplex_points[-1] = reflection
      else:
        # contraction case
        contraction = self.contraction_point()
        yield contraction
        while not driver.has_results(contraction):
          yield None # wait until results are ready

        if objective(contraction) < self.simplex_points[-1]:
          log.info("using contraction point")
          self.simplex_points[-1] = contraction
        else:
          #reduction case
          self.perform_reduction()
          log.info("reduction")
          for p in self.simplex_points:
            if not driver.has_results(p):
              yield p
          while not all(map(driver.has_results, self.simplex_points)):
            yield None # wait until results are ready

  def reflection_point(self):
    '''
    reflect worst point across centroid
    '''
    return self.linear_point(self.centroid, self.simplex_points[-1], self.alpha)

  def expansion_point(self):
    '''
    reflect worst point across centroid more (by default 2x as much)
    '''
    return self.linear_point(self.centroid, self.simplex_points[-1], self.gamma)

  def contraction_point(self):
    '''
    reflect worst point across centroid less, (by default goes backward by 1/2)
    '''
    return self.linear_point(self.centroid, self.simplex_points[-1], self.rho)

  def perform_reduction(self):
    '''
    shrink the simplex in size by sigma=1/2 (default), moving it closer to the
    best point
    '''
    for i in xrange(1, len(self.simplex_points)):
      self.simplex_points[i] = self.linear_point(
          self.simplex_points[0],
          self.simplex_points[i],
          -self.sigma
        )

  def convergence_criterea(self):
    '''True will cause the simplex method to stop'''
    return False

  @abc.abstractmethod
  def calculate_centroid(self):
    pass

  @abc.abstractmethod
  def linear_point(self, p1, p2, scale):
    '''
    return a point on the line passing between p1 and p2 at position scale
    such that p1 + scale*(p1 - p2)
    '''
    pass

  @abc.abstractmethod
  def initial_simplex(self):
    pass












