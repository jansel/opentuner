import abc
import logging

from fn import _

import opentuner
from opentuner.resultsdb.models import *

log = logging.getLogger(__name__)


class SearchObjective(object):
  '''
  delegates the comparison of results and configurations
  '''
  __metaclass__ = abc.ABCMeta

  @abc.abstractmethod
  def result_order_by_terms(self):
    '''return database columns required to order by the objective'''
    return []

  @abc.abstractmethod
  def result_compare(self, result1, result2):
    '''cmp() compatible comparison of resultsdb.models.Result'''
    return

  @abc.abstractmethod
  def config_compare(self, config1, config2):
    '''cmp() compatible comparison of resultsdb.models.Configuration'''
    return

  def __init__(self):
    self.driver = None

  def set_driver(self, driver):
    self.driver = driver

  def result_order_by(self, q):
    return q.order_by(*self.result_order_by_terms())

  def compare(self, a, b):
    '''cmp() compatible compare'''
    if isinstance(a, Configuration):
      return self.config_compare(a, b)
    if isinstance(a, Result):
      return self.result_compare(a, b)
    assert False

  def lt(self, a, b):  return self.compare(a, b) <  0
  def lte(self, a, b): return self.compare(a, b) <= 0
  def gt(self, a, b):  return self.compare(a, b) >  0
  def gte(self, a, b): return self.compare(a, b) >= 0

  def min(self, l):
    rv = l[0]
    for i in l[1:]:
      if self.lt(i, rv):
        rv = i
    return rv

  def max(self, l):
    rv = l[0]
    for i in l[1:]:
      if self.gt(i, rv):
        rv = i
    return rv

  def limit_from_config(self, config):
    '''
    a time limit to kill a result after such that it can be compared to config
    '''
    return max(map(_.time, self.driver.results_query(config=config)))


  def project_compare(self, a1, a2, b1, b2, factor=1.0):
    '''
    linearly project both a and b forward to see how they will compare in the
    future
    '''
    a3 = Result()
    b3 = Result()
    a3.time       = _project(a1.time,       a2.time,       factor)
    a3.accuracy   = _project(a1.accuracy,   a2.accuracy,   factor)
    a3.energy     = _project(a1.energy,     a2.energy,     factor)
    a3.confidence = _project(a1.confidence, a2.confidence, factor)
    return self.result_compare(a3, b3)

def _project(a1, a2, factor):
  if a1 is None or a2 is None:
    return None
  return a2 + factor*(a2-a1)

class MinimizeTime(SearchObjective):
  '''
  minimize Result().time
  '''

  def result_order_by_terms(self):
    '''return database columns required to order by the objective'''
    return [Result.time]

  def result_compare(self, result1, result2):
    '''cmp() compatible comparison of resultsdb.models.Result'''
    return cmp(result1.time, result2.time)

  def config_compare(self, config1, config2):
    '''cmp() compatible comparison of resultsdb.models.Configuration'''
    return cmp(min(map(_.time, self.driver.results_query(config=config1))),
               min(map(_.time, self.driver.results_query(config=config2))))


class ThresholdAccuracyMinimizeTime(SearchObjective):
  '''
  if accuracy >= target:
    minimize time
  else:
    maximize accuracy
  '''

  def __init__(self, accuracy_target, low_accuracy_limit_multiplier=10.0):
    self.accuracy_target = accuracy_target
    self.low_accuracy_limit_multiplier = low_accuracy_limit_multiplier
    super(ThresholdAccuracyMinimizeTime, self).__init__()

  def result_order_by_terms(self):
    '''return database columns required to order by the objective'''
    return ["min(accuracy, %f) desc" % self.accuracy_target,
            opentuner.resultsdb.models.Result.time]

  def result_compare(self, result1, result2):
    '''cmp() compatible comparison of resultsdb.models.Result'''
    return cmp((-min(self.accuracy_target, result1.accuracy), result1.time),
               (-min(self.accuracy_target, result2.accuracy), result2.time))

  def config_compare(self, config1, config2):
    '''cmp() compatible comparison of resultsdb.models.Configuration'''
    return self.result_compare(
        self.driver.results_query(config=config1, objective_ordered=True)[0],
        self.driver.results_query(config=config2, objective_ordered=True)[0])

  def limit_from_config(self, config):
    '''
    a time limit to kill a result after such that it can be compared to config
    '''
    results = self.driver.results_query(config=config)
    if self.accuracy_target > min(map(_.accuracy, results)):
      m = self.low_accuracy_limit_multiplier
    else:
      m = 1.0
    return m*max(map(_.time, results))





