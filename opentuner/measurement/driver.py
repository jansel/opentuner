import argparse
import logging
import time
import socket
import os
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
import sqlalchemy

from opentuner import resultsdb
from opentuner.driverbase import DriverBase
from opentuner.resultsdb.models import *

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--machine-class',
                       help="name of the machine class being run on")


class MeasurementDriver(DriverBase):
  '''
  manages the measurement process, reading DesiredResults and creating Results
  '''

  def __init__(self,
               measurement_interface,
               input_manager,
               **kwargs):
    super(MeasurementDriver, self).__init__(**kwargs)

    if not self.args.machine_class:
      self.args.machine_class = 'default'

    self.interface     = measurement_interface
    self.input_manager = input_manager
    self.commit        = self.tuning_run_main.commit
    self.upper_limit_multiplier = 10.0
    self.default_limit_multiplier = 2.0

    self.laptime = time.time()
    self.machine = self.get_machine()

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
                  memory_gb     = _memorysize()/(1024.0**3) if _memorysize() else 0,
                  machine_class = self.get_machine_class())
      self.session.add(m)
      return m


  def get_machine_class(self):
    '''
    get (or create) the machine class we are currently running on
    '''
    return MachineClass.get(self.session, name=self.args.machine_class)

  def run_time_limit(self, desired_result, default = 3600.0*24*365*10):
    '''return a time limit to apply to a test run (in seconds)'''
    best = self.results_query(objective_ordered = True).first()
    if best is None:
      if desired_result.limit:
        return desired_result.limit
      else:
        return default

    if desired_result.limit:
      return min(desired_result.limit, self.upper_limit_multiplier*best.time)
    else:
      return self.default_limit_multiplier*best.time

  def run_desired_result(self, desired_result):
    '''
    create a new Result using input manager and measurment interface
    '''
    desired_result.limit = self.run_time_limit(desired_result)

    input = self.input_manager.select_input(desired_result)
    self.session.add(input)
    self.session.flush()

    log.debug('running desired result %s on input %s', desired_result.id, input.id)

    self.input_manager.before_run(desired_result, input)

    result = self.interface.run(desired_result, input, desired_result.limit)
    result.configuration    = desired_result.configuration
    result.input            = input
    result.machine          = self.machine
    result.tuning_run       = self.tuning_run
    result.collection_date  = datetime.now()
    self.session.add(result)
    desired_result.result = result
    desired_result.state = 'COMPLETE'

    self.input_manager.after_run(desired_result, input)

    result.collection_cost = self.lap_timer()
    self.session.flush()#populate result.id
    log.debug('Result(id=%d, cfg=%d, time=%.4f, accuracy=%.2f, collection_cost=%.2f)',
             result.id,
             result.configuration.id,
             result.time,
             result.accuracy if result.accuracy is not None else float('NaN'),
             result.collection_cost)
    self.commit()

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
    self.commit()
    try:
      self.session.refresh(desired_result)
      if desired_result.state == 'REQUESTED':
        desired_result.state = 'RUNNING'
        desired_result.start_date = datetime.now()
        self.commit()
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


def _cputype():
  try:
    return re.search(r"model name\s*:\s*([^\n]*)",
                     open("/proc/cpuinfo").read()).group(1)
  except:
    pass
  try:
    # for OS X
    import subprocess
    return subprocess.Popen(["sysctl", "-n", "machdep.cpu.brand_string"], stdout=subprocess.PIPE).communicate()[0].strip()
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
    pass
  try:
    # for OS X
    import subprocess
    return subprocess.Popen(["sysctl", "-n", "hw.memsize"], stdout=subprocess.PIPE).communicate()[0].strip()
  except:
    log.warning("failed to get total memory")
    return None

