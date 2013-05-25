import abc
import hashlib
import re
import logging

from opentuner import resultsdb

log = logging.getLogger(__name__)

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

  @classmethod
  def main(cls, args, *pargs, **kwargs):
    from ..tuningrunmain import TuningRunMain
    return TuningRunMain(cls(args, *pargs, **kwargs), args).main()

