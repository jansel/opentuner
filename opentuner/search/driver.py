import argparse
from datetime import datetime
import logging

from fn import _

from opentuner import resultsdb
from opentuner.resultsdb.models import *
from opentuner.driverbase import DriverBase
import technique
import plugin

log = logging.getLogger(__name__)


argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--test-limit', type=int, default=5000,
    help='stop tuning after given tests count')
argparser.add_argument('--stop-after', type=float,
    help='stop tuning after given seconds')
argparser.add_argument('--parallelism', type=int, default=1, 
    help='how many tests to support at once')

class SearchDriver(DriverBase):
  '''
  controls the search process managing techniques and creating DesiredResults
  '''

  def __init__(self,
               manipulator,
               **kwargs):
    super(SearchDriver, self).__init__(**kwargs)

    self.manipulator = manipulator
    self.wait_for_results = self.tuning_run_main.results_wait
    self.commit = self.tuning_run_main.commit

    self.generation  = 0
    self.plugins     = plugin.get_enabled(self.args)
    self.techniques  = technique.get_enabled(self.args)
    self.plugins.sort(key = _.priority)
    self.techniques.sort(key = _.priority)
    self.objective.set_driver(self)

    for t in self.techniques:
      t.set_driver(self)


  def add_plugin(self, p):
    self.plugins.append(p)
    self.plugins.sort(key = _.priority)

  def convergence_criterea(self):
    '''returns true if the tuning process should stop'''
    if self.args.stop_after:
      elapsed = (datetime.now()-self.tuning_run.start_date).total_seconds()
      return elapsed > self.args.stop_after
    return self.generation > self.args.test_limit

  def active_techniques(self):
    '''returns list of techniques to use in the current generation'''
    return [t for t in self.techniques if t.is_ready()]

  def technique_budget(self, technique, techniques):
    '''determine budget of tests to allocate to technique'''
    return self.args.parallelism

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
      tdesired = [t.desired_result() for z in xrange(accounting.budget)]
      for d in tdesired:
        self.initialize_desired_result(t, d)
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

      self.plugin_proxy.on_result(r)
      for t in techniques:
        if t.name in requestors:
          self.plugin_proxy.on_result_for_technique(r, t)
          t.handle_result(r)
        else:
          t.handle_nonrequested_result(r)

  def has_results(self, config):
    return self.results_query(config=config).count()>0

  def run_generation(self):
    techniques = self.active_techniques()
    if len(techniques)==0:
      log.warning("no techniques active, skipping generation %d",
                  self.generation)
    else:
      self.plugin_proxy.before_techniques()
      desired = self.generate_desired_results(techniques)
      self.plugin_proxy.after_techniques()

      self.commit()

      self.plugin_proxy.before_results_wait()
      self.wait_for_results(self.generation)
      self.plugin_proxy.after_results_wait()

      self.result_handlers(techniques, self.generation)

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
    config = Configuration.get(self.session, self.program, hashv, cfg)
    assert config.data == cfg 
    return config

  def main(self):
    self.plugin_proxy.set_driver(self)
    self.plugin_proxy.before_main()
    while not self.convergence_criterea():
      self.run_generation()
      self.generation += 1
    self.plugin_proxy.after_main()






