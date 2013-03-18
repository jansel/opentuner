import logging
import argparse
from datetime import datetime
import time

from opentuner import resultsdb
from opentuner.search.driver import SearchDriver
from opentuner.measurement.driver import MeasurementDriver

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--label',
                       help="name for the TuningRun")
argparser.add_argument('--database',
                       help=("database to store tuning results in, see: "
  "http://docs.sqlalchemy.org/en/rel_0_8/core/engines.html#database-urls"))


class TuningRunMain(object):
  def __init__(self,
               manipulator,
               measurement_interface,
               input_manager,
               objective,
               args,
               search_driver = SearchDriver,
               measurement_driver = MeasurementDriver):

    if not args.database:
      args.database = 'sqlite://' #in memory

    if not args.label:
      args.label = 'unnamed'

    #self.fake_commit = ('sqlite' in args.database)
    self.fake_commit = True

    self.args = args

    self.engine, self.Session = resultsdb.connect(args.database)
    self.session = self.Session()
    self.tuning_run = None
    self.search_driver_cls = search_driver
    self.measurement_driver_cls = measurement_driver
    self.measurement_interface = measurement_interface
    self.input_manager = input_manager
    self.manipulator = manipulator
    self.objective = objective


  def init(self):
    if self.tuning_run is None:
      self.tuning_run  = (
        resultsdb.models.TuningRun(
          name            = self.args.label,
          args            = self.args,
          start_date      = datetime.now(),
          program_version = self.measurement_interface.program_version()
        ))
      self.session.add(self.tuning_run)

      self.search_driver = self.search_driver_cls(self.session,
                             self.tuning_run,
                             self.manipulator,
                             self.objective,
                             self,
                             self.args)

      self.measurement_driver = self.measurement_driver_cls(
                                  self.session,
                                  self.tuning_run,
                                  self.measurement_interface,
                                  self.input_manager,
                                  self,
                                  self.args)

  def commit(self, force = False):
    if force or not self.fake_commit:
      self.session.commit()
    else:
      self.session.flush()

  def main(self):
    if self.args.stats:
      import stats
      return stats.StatsMain(self.measurement_interface, self.args).main()

    self.init()
    try:
      self.tuning_run.state = 'RUNNING'
      self.commit(force=True)
      self.search_driver.main()
      self.tuning_run.state = 'COMPLETE'
    except:
      self.tuning_run.state = 'ABORTED'
      raise
    finally:
      self.tuning_run.end_date = datetime.now()
      self.commit(force=True)

  def results_wait(self, generation):
    '''called by search_driver to wait for results'''
    #single process version:
    self.measurement_driver.process_all()




