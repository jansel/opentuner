import abc
import logging
from collections import deque, defaultdict
from fn import _

from .technique import SearchTechniqueBase

log = logging.getLogger(__name__)

class MetaSearchTechnique(SearchTechniqueBase):
  """
  a technique made up of a collection of other techniques
  """
  def __init__(self, techniques, log_freq = 500, *pargs, **kwargs):
    super(MetaSearchTechnique, self).__init__(*pargs, **kwargs)
    self.techniques = techniques
    self.request_count = 0
    self.log_freq = log_freq
    self.logging_use_counters = defaultdict(int)
    self.unique_names()

  def unique_names(self):
    names = set()
    for t in self.techniques:
      while t.name in names:
        t.name += '~'
      t.name = intern(t.name)
      names.add(t.name)

  def set_driver(self, driver):
    super(MetaSearchTechnique, self).set_driver(driver)
    for t in self.techniques:
      t.set_driver(driver)
    self.driver = driver

  def desired_result(self):
    techniques = self.select_technique_order()
    for technique in techniques:
      dr = technique.desired_result()
      if dr is not None:
        if dr is False:
          # technique is waiting for results
          continue
        self.driver.register_result_callback(dr,
            lambda result: self.on_technique_result(technique, result))
        if self.log_freq:
          self.logging_use_counters[technique.name] += 1
          self.debug_log()
        self.request_count += 1
        return dr
      else:
        self.on_technique_no_desired_result(technique)
    return None

  def on_technique_no_desired_result(self, technique):
    """called if a sub-technique returns None"""
    pass

  def on_technique_result(self, technique, result):
    """callback for results of sub-techniques"""
    pass

  @abc.abstractmethod
  def select_technique_order(self):
    """select the order of next techniques to try"""
    return []

  def debug_log(self):
    if self.log_freq and sum(self.logging_use_counters.values())>self.log_freq:
      log.info("%s: %s", self.name,
          str(sorted(self.logging_use_counters.items(), key = _[1]*-1)))
      self.logging_use_counters = defaultdict(int)

class RoundRobinMetaSearchTechnique(MetaSearchTechnique):
  """evenly switch between all source techniques"""
  def __init__(self, techniques, **kwargs):
    techniques = deque(techniques)
    super(RoundRobinMetaSearchTechnique, self).__init__(techniques, **kwargs)

  def select_technique_order(self):
    rv = list(self.techniques)
    self.techniques.rotate(1)
    return rv

class RecyclingMetaTechnique(MetaSearchTechnique):
  """
  periodically restart techniques that are not performing well compared to
  global best
  """
  def __init__(self,
               techniques_generators,
               window = 100,
               factor = 5.0,
               **kwargs):
    if 'log_freq' not in kwargs:
      kwargs['log_freq'] = None
    techniques = deque((g(seed_cfg = None) for g in techniques_generators))
    self.rename_i = 0
    for t in techniques:
      self.rename_technique(t)
    super(RecyclingMetaTechnique, self).__init__(techniques, **kwargs)
    self.best_results = defaultdict(lambda: None)
    self.factor = factor
    self.last_check = 0
    self.old_best_results = defaultdict(lambda: None)
    self.technique_generators = deque(techniques_generators)
    self.window = window

  def rename_technique(self, technique):
    technique.name += ".R%d" % self.rename_i
    self.rename_i += 1

  def on_technique_result(self, technique, result):
    """callback for results of sub-techniques"""
    if (self.best_results[technique] is None or
        self.driver.objective.lt(result, self.best_results[technique])):
      self.best_results[technique] = result

  def technique_cmp(self, a, b):
  # a1 = self.old_best_results[a]
  # a2 = self.best_results[a]
  # b1 = self.old_best_results[b]
  # b2 = self.best_results[b]
  # if a1 is None and b1 is None:
  #   return 0
  # if a1 is None:
  #   return -1
  # if b1 is None:
  #   return 1
  # return self.driver.objective.project_compare(a1, a2, b1, b2, self.factor)

    # not ready techniques go to the back
    if not a.is_ready() or not b.is_ready():
      return cmp(b.is_ready(), a.is_ready())

    a = self.best_results[a]
    b = self.best_results[b]
    if a is None and b is None:
      return 0
    if a is None:
      return -1
    if b is None:
      return 1
    return self.driver.objective.compare(a, b)

  def recycle_techniques(self):
    techniques = list(self.techniques)
    techniques.sort(cmp=self.technique_cmp)
    worst = techniques[-1]

    if (not worst.is_ready()
        or (self.old_best_results[worst] is not None
            and self.driver.objective.lt(self.driver.best_result,
                                         self.best_results[worst]))):
      techniques_new = deque()
      tn = None
      for t, gen in zip(self.techniques, self.technique_generators):
        if t is worst:
          tn = gen(seed_cfg=self.driver.best_result.configuration.data)
          self.rename_technique(tn)
          tn.set_driver(self.driver)
          log.info("%s replacing %s with %s", self.name, t.name, tn.name)
          techniques_new.append(tn)
        else:
          techniques_new.append(t)
      self.techniques = techniques_new
    else:
      log.debug("%s: not replacing techniques", self.name)

    self.old_best_results = self.best_results
    self.best_results = defaultdict(lambda: None)
    for t in self.techniques:
      self.best_results[t] = self.old_best_results[t]

  def select_technique_order(self):
    """
    round robin between techniques
    """
    if self.last_check + self.window < self.request_count:
      self.last_check = self.request_count
      self.recycle_techniques()
    rv = list(self.techniques)
    self.techniques.rotate(1)
    self.technique_generators.rotate(1)
    return rv

