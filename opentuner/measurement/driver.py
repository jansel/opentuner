
import logging
from datetime import datetime
from opentuner import resultsdb
from opentuner.resultsdb.models import *
import time

log = logging.getLogger(__name__)

class MeasurementDriver(object):
  def __init__(self, session, measurement_interface, input_manager, args):
    self.session = session
    self.machine = None
    self.tuning_run = None
    self.args = args
    self.interface = measurement_interface
    self.input_manager = input_manager
    self.timer = time.time()
    super(MeasurementDriver, self).__init__()

  def run_desired_result(self, desired_result):
    input = self.input_manager.select_input(self, desired_result)
    self.session.add(input)
    self.session.flush()

    log.info('running desired result %s on input %s', desired_result.id, input.id)

    self.input_manager.before_run(self, desired_result, input)

    result = self.interface.run(self, desired_result, input)
    result.configuration    = desired_result.configuration
    result.input            = input
    result.machine          = self.machine
    result.tuning_run       = self.tuning_run
    result.collection_date  = datetime.now()
    self.session.add(result)
    self.input_manager.after_run(self, desired_result, input)

    t = time.time()
    result.collection_cost = t - self.timer 
    self.timer = t
    log.info('collection_cost %.2f seconds', result.collection_cost)


  def main(self):
    q = (self.session.query(DesiredResult)
         .order_by(DesiredResult.generation,
                   DesiredResult.priority.desc()))
    for desired_result in q:
      self.run_desired_result(desired_result)
      self.session.commit()


