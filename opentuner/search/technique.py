
import abc

from opentuner.resultsdb.models import *

class SearchTechniqueBase(object):
  '''
  abstract base class for search techniques, with minimal interface
  '''
  __metaclass__ = abc.ABCMeta
  
  def begin_generation(self, driver, generation):
    '''called at the start of a generation'''
    pass

  def end_generation(self, driver, generation):
    '''called at the end of a generation'''
    pass

  def is_ready(self, driver, generation):
    '''test if enough data has been gathered to use this technique'''
    return generation > 0

  @abc.abstractmethod
  def desired_results(self, manipulator, driver, count):
    """return at most count resultsdb.models.DesiredResult objects based on past performance"""
    return

class SearchTechnique(SearchTechniqueBase):
  '''
  a search search technique with basic utility functions
  '''
  
  def desired_results(self, manipulator, driver, count):
    '''call search_suggestion() count times'''
    return [self.desired_result(manipulator, driver, i) for i in xrange(count)]

  def desired_result(self, manipulator, driver, i):
    '''create and return a resultsdb.models.DesiredResult'''
    desired = DesiredResult()
    cfg, priority = self.desired_configuration(manipulator, driver, i)
    desired.configuration = driver.get_configuration(cfg)
    desired.priority      = float(priority)
    return desired

  @abc.abstractmethod
  def desired_configuration(self, manipulator, driver, i):
    '''
    return a (cfg, priority) that we should test
    given a ConfigurationManipulator, SearchDriver, and suggestion number
    '''
    return (dict(), 0.0)

class PureRandom(SearchTechnique):
  '''
  request configurations completely randomly
  '''
  def desired_configuration(self, manipulator, driver, i):
    '''return a (cfg, priority) that we should test'''
    return manipulator.random(), 0.0

class PureRandomInitializer(PureRandom):
  '''
  request configurations completely randomly, to form initial population
  '''
  def is_ready(self, driver, generation):
    '''only run this technique in generation 0'''
    return not super(PureRandomInitializer, self).is_ready(driver, generation)

def get_enabled(args):
  return [PureRandom(), PureRandomInitializer()]





