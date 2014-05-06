# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab autoindent smarttab
import abc
import multimethod

class Operator(object):
  def __init__(self):
    self.parameters = []; # parameter classes for which behavior is defined
  
  @abc.abstractmethod
  def apply_to(self, parameter):
    pass


