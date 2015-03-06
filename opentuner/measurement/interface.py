import abc
import argparse
import errno
import hashlib
import logging
import os
import re
import signal
import subprocess
import threading
import time
from multiprocessing.pool import ThreadPool

try:
  import resource
except ImportError:
  resource = None

try:
  import fcntl
except ImportError:
  fcntl = None

import opentuner
from opentuner import resultsdb

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--parallel-compile', action='store_true',
                       help="present if compiling can be done in parallel")

the_io_thread_pool = None


class MeasurementInterface(object):
  """
  abstract base class for compile and measurement
  """
  __metaclass__ = abc.ABCMeta

  def __init__(self,
               args=None,
               project_name=None,
               program_name='unknown',
               program_version='unknown',
               manipulator=None,
               objective=None,
               input_manager=None):
    self.args = args
    self._project = project_name
    self._program = program_name
    self._version = program_version
    self._objective = objective
    self._manipulator = manipulator
    self._input_manager = input_manager

    self.pids = []
    self.pid_lock = threading.Lock()
    self.parallel_compile = False

  def compile(self, config_data, id):
    """
    Compiles according to the configuration in config_data (obtained from
    desired_result.configuration) Should use id paramater to determine output
    location of executable Return value will be passed to run_precompiled
    as compile_result, useful for storing error/timeout information
    """
    pass

  def run_precompiled(self, desired_result, input, limit, compile_result, id):
    """
    Runs the given desired result on input and produce a Result() Abort
    early if limit (in seconds) is reached Assumes that the executable
    to be measured is already compiled in an executable corresponding to
    identifier id compile_result is the return result of compile(), will be
    None if compile was not called If id = None, must call run()
    """
    return self.run(desired_result, input, limit)

  def cleanup(self, id):
    """
    Clean up any temporary files associated with the executable
    """
    pass

  @abc.abstractmethod
  def run(self, desired_result, input, limit):
    """
    run the given desired_result on input and produce a Result(),
    abort early if limit (in seconds) is reached
    """
    return opentuner.resultdb.models.Result()

  def save_final_config(self, config):
    """
    called at the end of autotuning with the best resultsdb.models.Configuration
    """
    try:
      config_str = repr(config.data)
      if len(config_str) > 256:
        config_str = config_str[:256] + '...'
      log.info('final configuration: %s', config_str)
      log.info('you may want to implement save_final_config(), to store this')
    except:
      log.error('error printing configuration', exc_info=True)

  def db_program_version(self, session):
    """return a version identifier for the program being tuned"""
    return resultsdb.models.ProgramVersion.get(
        session=session,
        project=self.project_name(),
        name=self.program_name(),
        version=self.program_version(),
        parameter_info=self.manipulator().parameters_to_json(),
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
    """helper used to generate program versions"""
    return hashlib.sha256(open(filename).read()).hexdigest()

  def manipulator(self):
    """
    called once to create the search.manipulator.ConfigurationManipulator
    """
    if self._manipulator is None:
      msg = ('MeasurementInterface.manipulator() must be implemented or a '
             '"manipulator=..." must be provided to the constructor')
      log.error(msg)
      raise Exception(msg)
    return self._manipulator

  def objective(self):
    """
    called once to create the search.objective.SearchObjective
    """
    if self._objective is None:
      from ..search.objective import MinimizeTime

      return MinimizeTime()
    return self._objective

  def input_manager(self):
    """
    called once to create the measurement.inputmanager.InputManager
    """
    if self._objective is None:
      from .inputmanager import FixedInputManager

      return FixedInputManager()
    return self._input_manager

  def seed_configurations(self):
    """
    Extra seed configuration objects to add to those given on the command line.
    Configuration objects (typically dictionaries) not database objects.
    """
    return []

  def kill_all(self):
    self.pid_lock.acquire()
    for pid in self.pids:
      goodkillpg(pid)
    self.pids = []
    self.pid_lock.release()

  def call_program(self, cmd, limit=None, memory_limit=None, **kwargs):
    """
    call cmd and kill it if it runs for longer than limit

    returns dictionary like
      {'returncode': 0,
       'stdout': '', 'stderr': '',
       'timeout': False, 'time': 1.89}
    """
    the_io_thread_pool_init(self.args.parallelism)
    if limit is float('inf'):
      limit = None
    if type(cmd) in (str, unicode):
      kwargs['shell'] = True
    killed = False
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         preexec_fn=preexec_setpgid_setrlimit(memory_limit),
                         **kwargs)
    # Add p.pid to list of processes to kill in case of keyboardinterrupt
    self.pid_lock.acquire()
    self.pids.append(p.pid)
    self.pid_lock.release()

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
    finally:
      # No longer need to kill p
      self.pid_lock.acquire()
      if p.pid in self.pids:
        self.pids.remove(p.pid)
      self.pid_lock.release()

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


class DefaultMeasurementInterface(MeasurementInterface):
  def run(self, desired_result, input, limit):
    raise RuntimeError('MeasurementInterface.run() not implemented')


def preexec_setpgid_setrlimit(memory_limit):
  if resource is not None:
    def _preexec():
      os.setpgid(0, 0)
      try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
      except ValueError:
        pass  # No permission
      if memory_limit:
        try:
          (soft, hard) = resource.getrlimit(resource.RLIMIT_AS)
          resource.setrlimit(resource.RLIMIT_AS, (min(soft, memory_limit),
                                                  min(hard, memory_limit)))
        except ValueError:
          pass  # No permission
    return _preexec


def the_io_thread_pool_init(parallelism=1):
  global the_io_thread_pool
  if the_io_thread_pool is None:
    the_io_thread_pool = ThreadPool(2 * parallelism)
    # make sure the threads are started up
    the_io_thread_pool.map(int, range(2 * parallelism))


def goodkillpg(pid):
  """
  wrapper around kill to catch errors
  """
  log.debug("killing pid %d", pid)
  try:
    if hasattr(os, 'killpg'):
      os.killpg(pid, signal.SIGKILL)
    else:
      os.kill(pid, signal.SIGKILL)
  except:
    log.error('error killing process %s', pid, exc_info=True)


def goodwait(p):
  """
  python doesn't check if its system calls return EINTR, retry if it does
  """
  while True:
    try:
      rv = p.wait()
      return rv
    except OSError, e:
      if e.errno != errno.EINTR:
        raise

