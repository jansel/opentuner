import abc
import opentuner
from opentuner.resultsdb.models import *


class InputManager(object):
  """
  abstract base class for compile and measurement
  """
  __metaclass__ = abc.ABCMeta

  def set_driver(self, measurement_driver):
    self.driver = measurement_driver
    self.session = measurement_driver.session
    self.program = measurement_driver.tuning_run.program

  @abc.abstractmethod
  def select_input(self, desired_result):
    """
    select the input to be used to test desired_result
    """
    return opentuner.resultsdb.models.Input()


  def before_run(self, desired_result, input):
    """hook called before an input is used"""
    pass

  def after_run(self, desired_result, input):
    """hook called after an input is used"""
    pass

  def get_input_class(self):
    return None


class FixedInputManager(InputManager):
  """
  an input manage that produces a single input for all tests
  """

  def __init__(self,
               input_class_name='fixed',
               size=-1,
               path=None,
               extra=None):
    self.input_class_name = input_class_name
    self.size = size
    self.path = path
    self.extra = extra
    self.the_input = None
    super(FixedInputManager, self).__init__()


  def get_input_class(self):
    return InputClass.get(self.session,
                          program=self.program,
                          name=self.input_class_name,
                          size=self.size)

  def create_input(self, desired_result):
    """create the fixed input database object, result will be cached"""
    return Input(input_class=self.get_input_class(),
                 path=self.path,
                 extra=self.extra)

  def select_input(self, desired_result):
    if self.the_input is None:
      self.the_input = self.create_input(desired_result)
    return self.the_input






