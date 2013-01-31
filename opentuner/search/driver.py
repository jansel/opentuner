import argparse
from datetime import datetime
import logging

from fn import _
from opentuner import resultsdb
from opentuner.resultsdb.models import *
import technique
import plugin

log = logging.getLogger(__name__)

class SearchDriver(object):
  '''controls the search process'''

  def __init__(self,
               session,
               tuning_run,
               manipulator,
               results_wait,
               objective_order_by,
               args):
    self.session     = session
    self.tuning_run  = tuning_run
    self.manipulator = manipulator
    self.args        = args
    self.generation  = 0
    self.population  = []
    self.plugins     = plugin.get_enabled(args)
    self.techniques  = technique.get_enabled(args)
    self.wait_for_results = results_wait
    self.objective_order_by_terms = objective_order_by
    self.pipelining_cooldown = set()
    self.plugins.sort(key = lambda x: x.priority)
    self.techniques.sort(key = lambda x: x.priority)

  def add_plugin(self, p):
    self.plugins.append(p)
    self.plugins.sort(key = lambda x: x.priority)

  def convergence_criterea(self):
    '''returns true if the tuning process should stop'''
    return self.generation > self.args.generations

  def active_techniques(self):
    '''returns list of techniques to use in the current generation'''
    return [t for t in self.techniques
            if t.is_ready(self, self.generation)
            and t not in self.pipelining_cooldown]

  def technique_budget(self, technique, techniques):
    '''determine budget of tests to allocate to technique'''
    return self.args.population_size / len(techniques)

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
      accounting = TechniqueAccounting(
          tuning_run = self.tuning_run,
          generation = self.generation,
          budget = self.technique_budget(t, techniques),
          name = t.name,
          start_date = datetime.now(),
        )
      tdesired = t.desired_results(self.manipulator, self, accounting.budget)
      for d in tdesired:
        self.initialize_desired_result(t, d)
      self.rescale_technique_priorities(t, tdesired, accounting.budget)
      desired.extend(tdesired)
      self.session.add_all(tdesired)

      accounting.end_date = datetime.now()
      self.session.add(accounting)
    return desired

  def deduplicate_desired_results(self, desired_results):
    #TODO
    pass

  def result_handlers(self, techniques, generation):
    q = self.results_query(generation = generation)
    for r in q:
      desired_results = filter(_.tuning_run==self.tuning_run, r.desired_results)
      requestors = map(_.requestor, desired_results)
      log.debug("calling result handlers result Result %d, requested by %s",
                r.id, str(requestors))
      for t in techniques:
        if t.name in requestors:
          t.handle_result(r, self)
        else:
          t.handle_nonrequested_result(r, self)


  def results_query(self, generation = None, objective_ordered = False):
    q = self.session.query(Result)
    subq = (self.session.query(DesiredResult.result_id)
           .filter_by(tuning_run = self.tuning_run))
    if generation is not None:
      subq = subq.filter_by(generation = generation)
    q = q.filter(Result.id.in_(subq.subquery()))
    if objective_ordered:
      q = self.order_by_objective(q)
    return q

  def order_by_objective(self, q):
    return q.order_by(*self.objective_order_by_terms)

  def run_generation(self):
    self.plugin_proxy.before_generation(self)

    techniques = self.active_techniques()

    self.plugin_proxy.before_techniques(self)
    desired = self.generate_desired_results(techniques)
    self.plugin_proxy.before_techniques(self)

    self.session.commit()

    self.plugin_proxy.before_result_wait(self)
    self.wait_for_results(self.generation)
    self.plugin_proxy.after_result_wait(self)

    self.result_handlers(techniques, self.generation)

    self.plugin_proxy.after_generation(self)

  @property
  def plugin_proxy(self):
    '''
    forward any method calls on the returned object to all plugins
    '''
    plugins = self.plugins
    class PluginProxy(object):
      def __getattr__(self, method_name):
        def plugin_method_proxy(*args, **kwargs):
          rv = []
          for plugin in plugins:
            rv.append(getattr(plugin, method_name)(*args, **kwargs))
          return filter(lambda x: x is not None, rv)

        return plugin_method_proxy
    return PluginProxy()

  def get_configuration(self, cfg):
    '''called by SearchTechniques to create Configuration objects'''
    hashv = self.manipulator.hash_config(cfg)
    config = Configuration.get(self.session, hashv, cfg)
    assert config.data == cfg 
    return config

  def main(self):
    self.plugin_proxy.before_main(self)
    while not self.convergence_criterea():
      self.run_generation()
      self.generation += 1
    self.plugin_proxy.after_main(self)



argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--generations',     type=int, default=10)
argparser.add_argument('--population-size', type=int, default=10)





