import abc
import hashlib
import logging
import math
import os
import re
import select
import signal
import subprocess
import threading
import time
from multiprocessing.pool import ThreadPool

try:
  import resource
except:
  resource = None

try:
  import fcntl
except:
  fcntl = None

from opentuner import resultsdb
from opentuner.utils.socketpair_compat import socketpair

log = logging.getLogger(__name__)

the_io_thread_pool = None

class MeasurementInterface(object):
  '''
  abstract base class for compile and measurement
  '''
  __metaclass__ = abc.ABCMeta

  def __init__(self,
               args          = None,
               project_name  = None,
               program_name  = 'unknown',
               program_version = 'unknown',
               manipulator   = None,
               objective     = None,
               input_manager = None):
    self.args = args
    self._project       = project_name
    self._program       = program_name
    self._version       = program_version
    self._objective     = objective
    self._manipulator   = manipulator
    self._input_manager = input_manager


  @abc.abstractmethod
  def run(self, desired_result, input, limit):
    '''
    run the given desired_result on input and produce a Result(),
    abort early if limit (in seconds) is reached
    '''
    return opentuner.resultdb.models.Result()

  def save_final_config(self, config):
    '''
    called at the end of autotuning with the best resultsdb.models.Configuration
    '''
    pass

  def db_program_version(self, session):
    '''return a version identifier for the program being tuned'''
    return resultsdb.models.ProgramVersion.get(
        session = session,
        project = self.project_name(),
        name    = self.program_name(),
        version = self.program_version(),
      )

  def set_driver(self, measurement_driver):
    self.driver = measurement_driver

  def project_name(self):
    if self._project is not None:
      return self._project
    autoname = re.sub('(Measurement?)Interface$', '', self.__class__.__name__)
    if autoname:
      return autoname
    else:
      return 'unknown'

  def program_name(self):
    return self._program

  def program_version(self):
    return self._version

  def file_hash(self, filename):
    '''helper used to generate program versions'''
    return hashlib.sha256(open(filename).read()).hexdigest()

  def manipulator(self):
    '''
    called once to create the search.manipulator.ConfigurationManipulator
    '''
    if self._manipulator is None:
      msg = ('MeasurementInterface.manipulator() must be implemented or a '
             '"manipulator=..." must be provided to the constructor')
      log.error(msg)
      raise Exception(msg)
    return self._manipulator

  def objective(self):
    '''
    called once to create the search.objective.SearchObjective
    '''
    if self._objective is None:
      from ..search.objective import MinimizeTime
      return MinimizeTime()
    return self._objective

  def input_manager(self):
    '''
    called once to create the measurement.inputmanager.InputManager
    '''
    if self._objective is None:
      from .inputmanager import FixedInputManager
      return FixedInputManager()
    return self._input_manager

  def call_program(self, cmd, limit=None, memory_limit=None, **kwargs):
    '''
    call cmd and kill it if it runs for longer than limit

    returns dictionary like
      {'returncode': 0,
       'stdout': '', 'stderr': '',
       'timeout': False, 'time': 1.89}
    '''
    the_io_thread_pool_init()
    if limit is float('inf'):
      limit = None
    if type(cmd) in (str, unicode):
      kwargs['shell'] = True
    killed = False
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         preexec_fn=preexec_setpgid_setrlimit(memory_limit),
                         **kwargs)
    try:
      stdout_result = the_io_thread_pool.apply_async(p.stdout.read)
      stderr_result = the_io_thread_pool.apply_async(p.stderr.read)
      while p.returncode is None:
        if limit is None:
          goodwait(p)
        elif limit and time.time() > t0 + limit:
          killed = True
          goodkillpg(p.pid)
          goodwait(p)
        else:
          # still waiting...
          sleep_for = limit - (time.time() - t0)
          if not stdout_result.ready():
            stdout_result.wait(sleep_for)
          elif not stderr_result.ready():
            stderr_result.wait(sleep_for)
          else:
            #TODO(jansel): replace this with a portable waitpid
            time.sleep(0.001)
        p.poll()
    except:
      if p.returncode is None:
        goodkillpg(p.pid)
      raise

    t1 = time.time()
    return {'time': float('inf') if killed else (t1 - t0),
            'timeout': killed,
            'returncode': p.returncode,
            'stdout': stdout_result.get(),
            'stderr': stderr_result.get()}

  def prefix_hook(self, session):
    pass

  @classmethod
  def main(cls, args, *pargs, **kwargs):
    from opentuner.tuningrunmain import TuningRunMain
    return TuningRunMain(cls(args, *pargs, **kwargs), args).main()


def preexec_setpgid_setrlimit(memory_limit):
  if resource is not None:
    def _preexec():
        os.setpgid(0, 0)
        resource.setrlimit(resource.RLIMIT_CORE, (1,1))
        if memory_limit:
          resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    return _preexec

def the_io_thread_pool_init():
  global the_io_thread_pool
  if the_io_thread_pool is None:
    the_io_thread_pool = ThreadPool(2)
    # make sure the threads are started up
    the_io_thread_pool.map(int, range(2))

def goodkillpg(pid):
  '''
  wrapper around kill to catch errors
  '''
  log.debug("killing pid %d", pid)
  try:
    if hasattr(os, 'killpg'):
      os.killpg(pid, signal.SIGKILL)
    else:
      os.kill(pid, signal.SIGKILL)
  except:
    log.error('error killing process %s', pid, exc_info=True)


def goodwait(p):
  '''
  python doesn't check if its system calls return EINTR, retry if it does
  '''
  rv=None
  while True:
    try:
      rv=p.wait()
      return rv
    except OSError, e:
      if e.errno != errno.EINTR:
        raise

