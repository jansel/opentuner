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
argparser.add_argument('--parallelism', type=int, default=10,
    help='how many tests to support at once')

class SearchDriver(DriverBase):
  '''
  controls the search process managing root_technique and creating DesiredResults
  '''

  def __init__(self,
               manipulator,
               **kwargs):
    super(SearchDriver, self).__init__(**kwargs)

    self.manipulator = manipulator
    self.wait_for_results = self.tuning_run_main.results_wait
    self.commit = self.tuning_run_main.commit

    self.generation = 0
    self.test_count = 0
    self.plugins = plugin.get_enabled(self.args)
    self.pending_result_callbacks = list() # (DesiredResult, function) tuples
    self.root_technique = technique.get_root(self.args)
    self.objective.set_driver(self)
    self.pending_config_ids = set()

    for t in self.plugins:
      t.set_driver(self)
    self.root_technique.set_driver(self)

    self.plugins.sort(key = _.priority)

  def add_plugin(self, p):
    if p in self.plugins:
      return
    self.plugins.append(p)
    self.plugins.sort(key = _.priority)
    p.set_driver(self)

  def convergence_criterea(self):
    '''returns true if the tuning process should stop'''
    if self.args.stop_after:
      elapsed = (datetime.now()-self.tuning_run.start_date).total_seconds()
      return elapsed > self.args.stop_after
    return self.test_count > self.args.test_limit

  def register_result_callback(self, desired_result, callback):
    if desired_result.result is not None:
      callback(desired_result.result)
    else:
      self.pending_result_callbacks.append((desired_result, callback))

  def result_callbacks(self):
    pending = self.pending_result_callbacks
    self.pending_result_callbacks = list()
    for dr, callback in pending:
      if dr.result is not None:
        callback(dr.result)
      else:
        # try again later
        self.pending_result_callbacks.append((dr, callback))
    if len(self.pending_result_callbacks):
      log.warning("%d result callbacks still pending",
                  len(self.pending_result_callbacks))

    #q = self.results_query(generation = generation)
    #for r in q:
    #  desired_results = filter(_.tuning_run==self.tuning_run, r.desired_results)
    #  requestors = map(_.requestor, desired_results)
    #  log.debug("calling result handlers result Result %d, requested by %s",
    #            r.id, str(requestors))
    #  self.plugin_proxy.on_result(r)
    #  for t in techniques:
    #    if t.name in requestors:
    #      self.plugin_proxy.on_result_for_technique(r, t)
    #      t.handle_requested_result(r)

  def has_results(self, config):
    return self.results_query(config=config).count()>0

  def run_generation(self):
    self.plugin_proxy.before_techniques()
    for z in xrange(self.args.parallelism):
      dr = self.root_technique.desired_result()

      if dr is None:
        break

      self.session.flush() # populate configuration_id
      duplicates = list(self.session.query(DesiredResult)
                            .filter_by(tuning_run=self.tuning_run,
                                       configuration_id=dr.configuration_id)
                            .filter(DesiredResult.id != dr.id).limit(1))
      if len(duplicates):
        log.warning("duplicate configuration request %d %s", self.test_count, str(duplicates[0].result))
        def callback(result):
          dr.result     = result
          dr.state      = 'COMPLETE'
          dr.start_date = datetime.now()
        self.register_result_callback(duplicates[0], callback)
      else:
        dr.state = 'REQUESTED'
      self.session.add(dr)
      self.session.flush()
      self.test_count += 1
    self.plugin_proxy.after_techniques()

    self.commit()

    self.plugin_proxy.before_results_wait()
    self.wait_for_results(self.generation)
    self.plugin_proxy.after_results_wait()

    self.result_callbacks()

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






