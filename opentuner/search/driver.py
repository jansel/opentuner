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
#log.setLevel(logging.DEBUG)


argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--test-limit', type=int, default=5000,
    help='stop tuning after given tests count')
argparser.add_argument('--stop-after', type=float,
    help='stop tuning after given seconds')
argparser.add_argument('--parallelism', type=int, default=4,
    help='how many tests to support at once')
argparser.add_argument('--pipelining', type=int, default=0,
    help='how long a delay (in generations) before results are available')
argparser.add_argument('--bail-threshold', type=int, default=500,
    help='abort if no requests have been made in X generations')
argparser.add_argument('--no-dups', action='store_true',
    help='don\'t print out warnings for duplicate requests')

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
    self.best_result = None

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
      elapsed = (datetime.now()-self.tuning_run.start_date)
      try:
        elapsed = elapsed.total_seconds()
      except: #python 2.6
        elapsed = elapsed.days * 86400 + elapsed.seconds
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
        continue
      elif self.generation - dr.generation > self.args.pipelining:
        # see if we can find a result
        results = self.results_query(config=dr.configuration).all()
        log.warning("Result callback %d (requestor=%s) pending for "
                    "%d generations %d results available",
                    dr.id,
                    dr.requestor,
                    self.generation - dr.generation,
                    len(results))
        if len(results):
          dr.result = results[0]
          callback(dr.result)
          continue
      # try again later
      self.pending_result_callbacks.append((dr, callback))



  def has_results(self, config):
    return self.results_query(config=config).count()>0

  def run_generation_techniques(self):
    tests_this_generation = 0
    self.plugin_proxy.before_techniques()
    for z in xrange(self.args.parallelism):
      dr = self.root_technique.desired_result()
      if dr is None:
        log.debug("no desired result, skipping to testing phase")
        break
      self.session.flush() # populate configuration_id
      duplicates = (self.session.query(DesiredResult)
                            .filter_by(tuning_run=self.tuning_run,
                                       configuration_id=dr.configuration_id)
                            .filter(DesiredResult.id != dr.id)
                            .order_by(DesiredResult.request_date)
                            .limit(1)
                            .all())
      self.session.add(dr)
      if len(duplicates):
        if not self.args.no_dups:
          log.warning("duplicate configuration request #%d %s/%s %s",
                      self.test_count,
                      dr.requestor,
                      duplicates[0].requestor,
                      'OLD' if duplicates[0].result else 'PENDING')
        self.session.flush()
        desired_result_id = dr.id
        def callback(result):
          dr = self.session.query(DesiredResult).get(desired_result_id)
          dr.result     = result
          dr.state      = 'COMPLETE'
          dr.start_date = datetime.now()
        self.register_result_callback(duplicates[0], callback)
      else:
        log.debug("desired result id=%d, cfg=%d", dr.id, dr.configuration_id)
        dr.state = 'REQUESTED'
      self.test_count += 1
      tests_this_generation += 1
    self.plugin_proxy.after_techniques()
    return tests_this_generation

  def run_generation_results(self, offset = 0):
    self.commit()
    self.plugin_proxy.before_results_wait()
    self.wait_for_results(self.generation + offset)
    self.plugin_proxy.after_results_wait()

    for result in (self.results_query()
                  .filter_by(was_new_best = None)
                  .order_by(Result.collection_date)):
      if self.best_result is None:
        self.best_result = result
        result.was_new_best = True
      elif self.objective.lt(result, self.best_result):
        self.best_result = result
        result.was_new_best = True
        self.plugin_proxy.on_new_best_result(result)
      else:
        result.was_new_best = False

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
    return config

  def main(self):
    self.plugin_proxy.set_driver(self)
    self.plugin_proxy.before_main()

    no_tests_generations = 0

    # prime pipeline with tests
    for z in xrange(self.args.pipelining):
      self.run_generation_techniques()
      self.generation += 1

    while not self.convergence_criterea():
      if self.run_generation_techniques() > 0:
        no_tests_generations = 0
      elif no_tests_generations <= self.args.bail_threshold:
        no_tests_generations += 1
      else:
        break
      self.run_generation_results(offset = -self.args.pipelining)
      self.generation += 1

    self.plugin_proxy.after_main()






