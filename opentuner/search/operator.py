# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab autoindent smarttab
import abc
from multimethod import multimethod
from manipulator import Parameter, ConfigurationManipulator

class Operator(object):
  def __init__(self):
    self.parameters = []; # parameter classes for which behavior is defined
  
  @abc.abstractmethod
  def apply_to(self, param):
    pass

""" From Particle Swarm Optimization """
class SwarmMoveOperator(Operator):
  @multimethod(Operator, FloatParameter, *args)
  def apply_to(self, param, *args):
    pass

  @multimethod(Operator, IntegerParameter, *args)
  def apply_to(self, param, *args):
    pass

  @multimethod(Operator, PermutationParameter, *args)
  def apply_to(self, param, *args):
    pass

""" From Genetic Algorithm """
class CrossoverOperator(Operator):
  @multimethod(CrossoverOperator, PermutationParameter, *args)
  def apply_to(self, param, *args):
    pass



""" From Differential Evolution """
class DifferenceCrossoverOperator(Operator):
  @multimethod(DifferenceCrossoverOperator, ConfigurationManipulator, *args)
  def apply_to(self, param, *args):
    pass


def list_operators():
  """
  Return all operators implemented in current module (operator.py)
  """
  pass

def list_param_operators(param):
  """ 
  Return operators applicable to given Parameter class
  """
  pass

def list_config_operators():
  """
  Return operators applicable to Configuration
  """
  pass



