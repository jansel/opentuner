import abc
import copy
import random
import time
import logging
from fn import _
from opentuner.resultsdb.models import *
from technique import SearchTechnique

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)

class PopulationMember(object):
  def __init__(self, config, submitted = True):
    self.config = config
    self.submitted = submitted
    self.timestamp = time.time()
    self.candidate_replacement = None

  def touch(self):
    self.timestamp = time.time()

class DifferentialEvolution(SearchTechnique):
  '''
  based on http://cci.lbl.gov/cctbx_sources/scitbx/differential_evolution.py
  '''
  def __init__(self,
               population_size=30,
               cr=0.9, # crossover rate
               n_cross=1, # force at least 1 to crossover
              ):
    self.population_size = population_size
    self.cr = cr
    self.n_cross = n_cross
    self.population = None
    super(DifferentialEvolution, self).__init__()

  def initial_population(self, manipulator, driver):
    self.population = [
        PopulationMember(driver.get_configuration(manipulator.random()),
                         submitted = False)
        for z in xrange(self.population_size)
      ]

  def oldest_pop_member(self):
    # since tests are run in parallel, exclude things with a replacement pending
    pop_without_replacements = filter(lambda x: x.candidate_replacement is None,
                                      self.population)
    if not pop_without_replacements:
      # everything has a pending replacement
      return None
    pop_without_replacements.sort(key = _.timestamp)
    return pop_without_replacements[0]

  def desired_configuration(self, manipulator, driver):
    '''
    return a cfg that we should test,
    '''
    if not self.population:
      # first time called
      self.initial_population(manipulator, driver)

    # make sure initial population is completely submitted
    for p in self.population:
      if not p.submitted:
        p.submitted = True
        if p is self.population[-1]:
          log.info("initial population testing done")
        return p.config

    # pp is member of population to be replaced
    pp = self.oldest_pop_member()
    if not pp: return None
    cfg = manipulator.copy(pp.config.data)
    cfg_params = manipulator.proxy(cfg)

    # pick 3 random parents, not pp
    shuffled_pop = list(set(self.population) - set([pp]))
    random.shuffle(shuffled_pop)
    x1, x2, x3 = map(_.config.data, shuffled_pop[0:3])

    use_f = random.random()/2.0 + 0.5

    params = manipulator.param_names(cfg, x1, x2, x3)
    random.shuffle(params)
    for i, k in enumerate(params):
      if i<self.n_cross or random.random() < self.cr:
        # cfg = x1 + use_f*(x2 - x3)
        cfg_params[k].set_linear(1.0, x1, use_f, x2, -use_f, x3)

    pp.touch() # move to back of the line for next replacement
    pp.candidate_replacement = driver.get_configuration(cfg)
    self.limit = driver.objective.limit_from_config(pp.config)
    return pp.candidate_replacement

  def handle_result(self, result, driver):
    '''called when new results are added'''
    for p in self.population:
      if p.candidate_replacement == result.configuration:
        if driver.objective.lt(p.candidate_replacement, p.config):
          # candidate replacement was better, replace it!
          p.config = p.candidate_replacement
          log.info("better point")
        p.candidate_replacement = None

  def is_ready(self, driver, generation):
    return True

