import argparse
from datetime import datetime
import logging

from opentuner import resultsdb
from opentuner.resultsdb.models import *
import technique

log = logging.getLogger(__name__)

class SearchDriver(object):
  '''controls the search process'''

  def __init__(self, manipulator, args):
    self.engine, self.Session = resultsdb.connect()
    self.session     = self.Session()
    self.manipulator = manipulator
    self.generation  = 0
    self.args        = args
    self.population  = []
    self.techniques  = technique.get_enabled(args)
    self.pipelining_cooldown = set()
    self.tuning_run  = TuningRun(start_date=datetime.now(),
                                 args=args)

  def convergence_criterea(self):
    '''returns true if the tuning process should stop'''
    return self.generation > self.args.generations

  def active_techniques(self):
    '''returns list of techniques to use in the current generation'''
    return [t for t in self.techniques 
            if t.is_ready(self, self.generation) 
            and t not in self.pipelining_cooldown]

  def technique_budget(self, technique):
    '''determine budget of tests to allocate to technique'''
    return self.args.population_size

  def rescale_technique_priorities(self, technique, desired_results, budget):
    '''normalize the priorities output by the techniques so they sum to 1.0'''
    priorities = map(lambda x: x.priority, desired_results)
    minp = float(min(priorities))
    maxp = float(max(priorities))
    sump = float(sum(priorities))
    lenp = float(len(priorities))
    for dr in desired_results:
      if minp==maxp:
        dr.priority = 1.0/lenp
      else:
        dr.priority -= minp
        dr.priority *= 1.0/(sump-(lenp*minp))
  
  def initialize_desired_result(self, technique, dr):
    '''initialize a DesiredResult created by a SearchTechnique'''
    if dr.priority is not None:
      dr.priority_raw = dr.priority
    dr.priority     = dr.priority_raw
    dr.generation   = self.generation
    dr.requestor    = technique.name
    dr.request_date = datetime.now()
    dr.tuning_run   = self.tuning_run

  def generate_desired_results(self, techniques):
    '''get DesiredResult objects from each technique'''
    desired = list()
    for t in techniques:
      budget = self.technique_budget(t)
      tdesired = t.desired_results(self.manipulator, self, budget)
      for d in tdesired:
        self.initialize_desired_result(t, d)
      self.rescale_technique_priorities(t, tdesired, budget)
      desired.extend(tdesired)
    self.session.add_all(desired)
    return desired

  def technique_hooks(self, techniques, fname, gen=None):
    '''call fname on each technique'''

    if gen is None:
      gen = self.generation

    fname = intern(fname)
    
    log.debug("%s %d hooks", fname, gen)

    for t in techniques:
      getattr(t, fname)(self, gen)


  def deduplicate_desired_results(self, desired_results):
    #TODO
    pass

  def wait_for_results(self, gen):
    #TODO
    pass

  def run_generation(self):
    techniques = self.active_techniques()

    self.technique_hooks(techniques, 'begin_generation')

    desired = self.generate_desired_results(techniques)

    self.technique_hooks(techniques, 'mid_generation')
    self.session.commit()
    self.wait_for_results(self.generation)

    self.technique_hooks(techniques, 'end_generation')

  def get_configuration(self, cfg):
    '''called by SearchTechniques to create Configuration objects'''
    hashv = self.manipulator.hash_config(cfg)
    config = Configuration.get(self.session, hashv, cfg)
    assert config.data == cfg 
    return config

  def main(self):
    while not self.convergence_criterea():
      self.run_generation()
      self.generation += 1



argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--generations',     type=int, default=1)
argparser.add_argument('--population-size', type=int, default=3)





