import abc
from opentuner.resultsdb.models import *

class InputManager(object):
  '''
  abstract base class for compile and measurement
  '''
  __metaclass__ = abc.ABCMeta

  @abc.abstractmethod
  def select_input(self, measurement_driver, desired_result):
    '''
    select the input to be used to test desired_result
    '''
    return opentuner.resultsdb.models.Input()


  def before_run(self, measurement_driver, desired_result, input):
    '''hook called before an input is used'''
    pass

  def after_run(self, measurement_driver, desired_result, input):
    '''hook called after an input is used'''
    pass

class FixedInputManager(InputManager):
  '''
  an input manage that produces a single input for all tests
  '''
  def __init__(self,
               input_class_name='fixed',
               size  = -1,
               path  = None,
               extra = None):
    self.input_class_name = input_class_name
    self.size  = size
    self.path  = path
    self.extra = extra
    self.the_input = None
    super(FixedInputManager, self).__init__()

  def create_input(self, driver, desired_result):
    '''create the fixed input database object, result will be cached'''
    input_class = InputClass.get(driver.session,
                                 driver.tuning_run.program,
                                 name=self.input_class_name,
                                 size=self.size)
    return Input(input_class = input_class,
                 path  = self.path,
                 extra = self.extra)

  def select_input(self, driver, desired_result):
    if self.the_input is None:
      self.the_input = self.create_input(driver, desired_result)
    return self.the_input





