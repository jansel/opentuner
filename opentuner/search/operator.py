# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab autoindent smarttab
import abc
from multimethod import multimethod
from manipulator import Parameter, ConfigurationManipulator

class Operator(object):
  @abc.abstractmethod
  def apply_to(self, param):
    #TODO: handling incompatible parameters
    pass

""" From Particle Swarm Optimization """
class SwarmMove(Operator):
  @multimethod(Operator, FloatParameter, *args)
  def apply_to(self, param, position, global_best, local_best, omega, phi_g, phi_l, velocity):
    v = omega*param.get_value(velocity)+phi_g*param.get_value(global_best)+phi_l*param.get_value(local_best)
    param.set_value( position, v+param.get_value(position))
    return v

  @multimethod(Operator, IntegerParameter, *args)
  def apply_to(self, param, *args):
    k = p.nvalues()
    # Map position to discrete space
    n1 = k/(1+exp(-self.position))
    # Add Gaussian noise and round
    n2 = round(random.gauss(c, sigma*(k-1)))
    n3 = min(k, max(n2, 1))
    p.set_value(n3, self.position)


  @multimethod(Operator, str, PermutationParameter, dict, dict,dict,float, float )
  def apply_to(self, c_choice, param, position, global_best, local_best, omega,phi_l):
    if random.uniform(0,1)>omega:
      if random.uniform(0,1)<phi_l:
        # Select crossover operator
        getattr(p, c_choice)(position, position, global_best, d=p.size/3)
      else:
        getattr(p, c_choice)(position, position, local_best, d=p.size/3)


""" From Genetic Algorithm """
class Crossover(Operator):
  @multimethod(CrossoverOperator, PermutationParameter, dict, dict, dict, str)
  def apply_to(self, param, dest, cfg1, cfg2, c_choice):
    getattr(param, c_choice)(dest, cfg1, cfg2, d=param.size/3)



""" From Differential Evolution """
class DifferenceCrossover(Operator):
  @multimethod(DifferenceCrossoverOperator, ConfigurationManipulator, *args)
  def apply_to(self, param, *args):
    pass

class Mutate(Operator):
  
  def apply_to(self, param, dest, strengh)

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



