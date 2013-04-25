import argparse
import logging
import os
import socket
import time
import uuid
from datetime import datetime

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
      #args.database = 'sqlite://' #in memory
      if not os.path.isdir('opentuner.db'):
        os.mkdir('opentuner.db')
      args.database = 'sqlite:///'+os.path.join('opentuner.db', socket.gethostname()+'.db')

    if '://' not in args.database:
      args.database = 'sqlite:///'+args.database

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
      program_version = (self.measurement_interface
                            .db_program_version(self.session))
      self.session.flush()
      self.tuning_run  = (
        resultsdb.models.TuningRun(
          uuid            = uuid.uuid4().hex,
          name            = self.args.label,
          args            = self.args,
          start_date      = datetime.now(),
          program_version = program_version,
        ))
      self.session.add(self.tuning_run)

      driver_kwargs = {
          'args'                  : self.args,
          'input_manager'         : self.input_manager,
          'manipulator'           : self.manipulator,
          'measurement_interface' : self.measurement_interface,
          'objective'             : self.objective,
          'session'               : self.session,
          'tuning_run_main'       : self,
          'tuning_run'            : self.tuning_run,
        }

      self.search_driver = self.search_driver_cls(**driver_kwargs)

      self.measurement_driver = self.measurement_driver_cls(**driver_kwargs)
      self.measurement_interface.set_driver(self.measurement_driver)
      self.input_manager.set_driver(self.measurement_driver)

      self.tuning_run.machine_class = self.measurement_driver.get_machine_class()
      self.tuning_run.input_class = self.input_manager.get_input_class()

  def commit(self, force = False):
    if force or not self.fake_commit:
      self.session.commit()
    else:
      self.session.flush()

  def main(self):
    if self.args.stats:
      import stats
      return stats.StatsMain(self.measurement_interface,
                             self.session,
                             self.args).main()

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




