import argparse
import logging
import time
import socket
import os 
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
import sqlalchemy

from opentuner import resultsdb
from opentuner.resultsdb.models import *

log = logging.getLogger(__name__)

class MeasurementDriver(object):
  def __init__(self,
               session,
               tuning_run,
               measurement_interface,
               input_manager,
               args):

    if not args.machine_class:
      args.machine_class = 'default'

    self.session = session
    self.tuning_run = tuning_run
    self.args = args
    self.interface = measurement_interface
    self.input_manager = input_manager
    self.laptime = time.time()
    self.machine = self.get_machine()
    super(MeasurementDriver, self).__init__()

  def get_machine(self):
    '''
    get (or create) the machine we are currently running on
    '''
    hostname = socket.gethostname()
    try:
      self.session.flush()
      return self.session.query(Machine).filter_by(name=hostname).one()
    except sqlalchemy.orm.exc.NoResultFound: 
      m = Machine(name          = hostname,  
                  cpu           = _cputype(),
                  cores         = _cpucount(),
                  memory_gb     = _memorysize()/(1024.0**3),
                  machine_class = self.get_machine_class())
      self.session.add(m)
      return m


  def get_machine_class(self):
    '''
    get (or create) the machine class we are currently running on
    '''
    return MachineClass.get(self.session, name=self.args.machine_class)

  def run_desired_result(self, desired_result):
    '''
    create a new Result using input manager and measurment interface
    '''
    input = self.input_manager.select_input(self, desired_result)
    self.session.add(input)
    self.session.flush()

    log.debug('running desired result %s on input %s', desired_result.id, input.id)

    self.input_manager.before_run(self, desired_result, input)

    result = self.interface.run(self, desired_result, input)
    result.configuration    = desired_result.configuration
    result.input            = input
    result.machine          = self.machine
    result.tuning_run       = self.tuning_run
    result.collection_date  = datetime.now()
    self.session.add(result)
    desired_result.result = result
    desired_result.state = 'COMPLETE'

    self.input_manager.after_run(self, desired_result, input)
    
    result.collection_cost = self.lap_timer()
    self.session.flush()#populate result.id
    log.info('Result(id=%d, cfg=%d, time=%.4f, accuracy=%.2f, collection_cost=%.2f)',
             result.id,
             result.configuration.id,
             result.time,
             result.accuracy,
             result.collection_cost)
    self.session.commit()

  def lap_timer(self):
    '''return the time elapsed since the last call to lap_timer'''
    t = time.time()
    r = t - self.laptime
    self.laptime = t
    return r

  def claim_desired_result(self, desired_result):
    '''
    claim a desired result by changing its state to running
    return True if the result was claimed for this process
    '''
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
    '''
    process all desired_results in the database
    '''
    self.lap_timer() #reset timer
    q = (self.session.query(DesiredResult)
         .filter_by(tuning_run = self.tuning_run,
                    state = 'REQUESTED')
         .order_by(DesiredResult.generation,
                   DesiredResult.priority.desc()))
    for dr in q.all():
      if self.claim_desired_result(dr):
        self.run_desired_result(dr)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--machine-class',
                       help="name of the machine class being run on")


def _cputype():
  try:
    return re.search(r"model name\s*:\s*([^\n]*)",
                     open("/proc/cpuinfo").read()).group(1)
  except:
    log.warning("failed to get cpu type")
    return None

def _cpucount():
  try:
    return os.sysconf("SC_NPROCESSORS_ONLN")
  except:
    pass
  try:
    return os.sysconf("_SC_NPROCESSORS_ONLN")
  except:
    pass
  try:
    return int(os.environ["NUMBER_OF_PROCESSORS"])
  except:
    pass
  try:
    return int(os.environ["NUM_PROCESSORS"])
  except:
    log.warning("failed to get the number of processors")
  return None

def _memorysize():
  try:
    return os.sysconf("SC_PHYS_PAGES")*os.sysconf("SC_PAGE_SIZE")
  except:
    pass
  try:
    return os.sysconf("_SC_PHYS_PAGES")*os.sysconf("_SC_PAGE_SIZE")
  except:
    log.warning("failed to get total memory")
    return None

