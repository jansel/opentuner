import abc
import hashlib

from opentuner import resultsdb

class MeasurementInterface(object):
  '''
  abstract base class for compile and measurement
  '''
  __metaclass__ = abc.ABCMeta

  @abc.abstractmethod
  def run(self, measurement_driver, desired_result, input):
    '''
    run the given desired_result on input and produce a Result()
    '''
    return opentuner.resultdb.models.Result()

  def program_version(self):
    '''return a version identifier for the program being tuned'''
    return 'unknown'

  def file_hash(self, filename):
    '''helper used to generate program versions'''
    return hashlib.sha256(open(filename).read()).hexdigest()



