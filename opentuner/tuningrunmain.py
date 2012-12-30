import logging
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
    self.tuning_run  = resultsdb.models.TuningRun(start_date=datetime.now(),
                                                  args=args)
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
    self.search_driver.main()

  def results_wait(self, generation):
    '''called by search_driver to wait for results'''
    #single process version:
    self.measurement_driver.process_all()


