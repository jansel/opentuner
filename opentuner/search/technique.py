
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

  def mid_generation(self, driver, generation):
    '''called after techniques have run, before results have been gathered'''
    pass

  def end_generation(self, driver, generation):
    '''called at the end of a generation'''
    pass

  def is_ready(self, driver, generation):
    '''test if enough data has been gathered to use this technique'''
    return generation > 0

  @abc.abstractmethod
  def desired_results(self, manipulator, driver, count):
    """
    return at most count resultsdb.models.DesiredResult objects based on past
    performance
    """
    return

  @property
  def name(self):
    '''name of this SearchTechnique uses for display/accounting'''
    return self.__class__.__name__

  @property
  def allow_pipelining(self):
    '''true if technique supports overlapping generations, with delayed results'''
    return True

  @abc.abstractmethod
  def handle_result(self, result, requestor_name, driver):
    '''called for each new Result(), regardless of who requested it'''
    pass
    
  

class SearchTechnique(SearchTechniqueBase):
  '''
  a search search technique with basic utility functions
  '''
  
  def desired_results(self, manipulator, driver, count):
    '''call search_suggestion() count times'''
    return [self.desired_result(manipulator, driver, i) for i in xrange(count)]

  def desired_result(self, manipulator, driver, i):
    '''create and return a resultsdb.models.DesiredResult'''
    cfg, priority = self.desired_configuration(manipulator, driver, i)
    config = driver.get_configuration(cfg)
    desired = DesiredResult()
    desired.configuration = config
    desired.priority_raw  = float(priority)
    return desired

  @abc.abstractmethod
  def desired_configuration(self, manipulator, driver, i):
    '''
    return a (cfg, priority) that we should test
    given a ConfigurationManipulator, SearchDriver, and suggestion number
    '''
    return (dict(), 0.0)

  def handle_result(self, result, driver):
    '''called for each new Result(), regardless of who requested it'''
    pass

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
    return generation==0


class EvolutionaryTechnique(SearchTechnique):

  
  def desired_configuration(self, manipulator, driver, i):
    '''
    return a (cfg, priority) that we should test,
    through random mutation and crossover
    '''
    parents = self.selection(driver, i)

    if len(parents) > 1:
      parent = self.crossover(parents)
    else:
      parent = parents[0]

  @abc.abstractmethod
  def selection(self, driver, i):
    '''
    return a list of parent configurations to use
    '''
    return []




def get_enabled(args):
  return [PureRandom(), PureRandomInitializer()]





