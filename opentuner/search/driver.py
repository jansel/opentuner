import argparse

from opentuner import resultsdb
from opentuner.resultsdb.models import *

import technique

class SearchDriver(object):
  '''controls the search process'''

  def __init__(self, manipulator, args):
    self.engine, self.Session = resultsdb.connect()
    self.session       = self.Session()
    self.manipulator   = manipulator
    self.generation    = 0
    self.args          = args
    self.population    = []
    self.techniques    = technique.get_enabled(args)

  def convergence_criterea(self):
    '''returns true if the tuning process should stop'''
    return self.generation > self.args.generations

  def active_techniques(self):
    '''returns list of techniques to use in the current generation'''
    return filter(lambda x: x.is_ready(self, self.generation),
                  self.techniques)

  def technique_budget(self, technique):
    return self.args.population_size

  def rescale_technique_priorities(self, technique, desired_results):
    pass
  
  def run_generation(self):
    techniques = self.active_techniques()

    for t in techniques:
      t.begin_generation(self, self.generation) 

    desired = list()
    for t in techniques:
      tdesired = t.desired_results(self.manipulator, self, self.technique_budget(t))
      self.rescale_technique_priorities(t, tdesired)
      desired.extend(tdesired)


    self.session.add_all(desired)
    self.session.commit()

    for t in techniques:
      t.end_generation(self, self.generation) 

  def get_configuration(self, cfg):
    cfg = Configuration()
    cfg.data = cfg
    self.session.add(cfg)
    self.session.commit()
    return cfg.id

  def main(self):
    while not self.convergence_criterea():
      self.run_generation()
      self.generation += 1



argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--generations',     type=int, default=1)
argparser.add_argument('--population-size', type=int, default=3)





