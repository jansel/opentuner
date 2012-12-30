
import logging
from datetime import datetime
from opentuner import resultsdb
from opentuner.resultsdb.models import *
import time

from sqlalchemy.exc import SQLAlchemyError

log = logging.getLogger(__name__)

class MeasurementDriver(object):
  def __init__(self,
               session,
               tuning_run,
               machine,
               measurement_interface,
               input_manager,
               args):
    self.session = session
    self.machine = machine
    self.tuning_run = tuning_run
    self.args = args
    self.interface = measurement_interface
    self.input_manager = input_manager
    self.laptimer = time.time()
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
    result.collection_cost = t - self.laptimer 
    self.laptimer = t
    log.info('collection_cost %.2f seconds', result.collection_cost)

    desired_result.result = result
    desired_result.state = 'COMPLETE'

  def claim_desired_result(self, desired_result):
    self.session.commit()
    try:
      self.session.refresh(desired_result)
      if desired_result.state == 'REQUESTED':
        desired_result.state = 'RUNNING'
        desired_result.start_date = datetime.now()
        self.session.commit()
        return True
    except SQLAlchemyError: 
      self.session.rollback()
    return False

  def process_all(self):
    q = (self.session.query(DesiredResult)
         .filter_by(tuning_run = self.tuning_run,
                    state = 'REQUESTED')
         .order_by(DesiredResult.generation,
                   DesiredResult.priority.desc()))
    for dr in list(q):
      if self.claim_desired_result(dr):
        self.run_desired_result(dr)
        self.session.commit()


