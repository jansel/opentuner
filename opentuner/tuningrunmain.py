import logging
import argparse
from datetime import datetime

from opentuner import resultsdb
from opentuner.search.driver import SearchDriver
from opentuner.measurement.driver import MeasurementDriver
import time

log = logging.getLogger(__name__)


class TuningRunMain(object):
  def __init__(self,
               manipulator,
               measurement_interface,
               input_manager,
               args,
               search_driver = SearchDriver,
               measurement_driver = MeasurementDriver):

    self.engine, self.Session = resultsdb.connect()
    self.session = self.Session()

    self.tuning_run  = (
      resultsdb.models.TuningRun(
        name            = args.label,
        args            = args,
        start_date      = datetime.now(),
        program_version = measurement_interface.program_version()
      ))
    self.session.add(self.tuning_run)

    self.session.commit()
    self.search_driver = search_driver(self.Session(),
                                       self.tuning_run,
                                       manipulator,
                                       self.results_wait,
                                       args)
    self.measurement_driver = measurement_driver(self.Session(),
                                                 self.tuning_run,
                                                 measurement_interface,
                                                 input_manager,
                                                 args)

  def main(self):
    try:
      self.search_driver.main()
      self.tuning_run.state = 'COMPLETE'
    except:
      self.tuning_run.state = 'ABORTED'
      raise
    finally:
      self.tuning_run.end_date = datetime.now()
      self.session.commit()

  def results_wait(self, generation):
    '''called by search_driver to wait for results'''
    #single process version:
    self.measurement_driver.process_all()

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--label', default="unnamed", 
                       help="name for the TuningRun")





