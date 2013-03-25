import abc
import hashlib
import re

from opentuner import resultsdb


class MeasurementInterface(object):
  '''
  abstract base class for compile and measurement
  '''
  __metaclass__ = abc.ABCMeta

  def __init__(self,
               args    = None,
               project = None,
               program = 'unknown',
               version = 'unknown'):
    self.args = args
    self._project = project
    self._program = program
    self._version = version


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



