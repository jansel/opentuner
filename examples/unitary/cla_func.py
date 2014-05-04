import numpy as np
import math


class Op:
  def __init__(self):
    self.M = []
    self.name = [];
    self.mutation_partners = [];
    self.anti_operator = [];

    self.mutation_partners_no = []
    self.anti_operator_no = []

    # create all operators
    self.create_operators()

    # check unitarity of all operators
    self.check_unitarity()

    # determine the indices of the mutation partners
    self.determine_index_of_mutation_partners()

    # determine the indices of the anti-operators
    self.determine_index_of_anti_operators()


  def create_operators(self):

    # example with +Z
    #self.M.append(np.matrix([[1.0, 2.0], [2.0+2.0j, 3.0]]))
    # watch out: python needs 1.0 instead of just 1 to assume float variables
    #self.name.append('asd');
    #self.mutation_partners.append(['+z','+w']);
    #self.anti_operator.append('+w');

    # Operators
    alpha = math.pi / 3.0;
    da = math.pi / 10.0;

    # operator 1 +z
    self.M.append(np.matrix(
      [[math.cos(da / 2.0) - 1j * math.sin(da / 2.0), 0.0],
       [0.0, math.cos(da / 2.0) + 1j * math.sin(da / 2.0)]]))
    self.name.append('+z');
    self.mutation_partners.append(['-z', '+w', '-w']);
    self.anti_operator.append('-z');

    # operator 2 -z
    self.M.append(np.matrix(
      [[math.cos(-da / 2.0) - 1j * math.sin(-da / 2.0), 0.0],
       [0.0, math.cos(-da / 2.0) + 1j * math.sin(-da / 2.0)]]))
    self.name.append('-z');
    self.mutation_partners.append(['+z', '+w', '-w']);
    self.anti_operator.append('+z');

    # operator 3 +w
    self.M.append(np.matrix([
      [math.cos(da / 2.0) - 1j * math.cos(alpha) * math.sin(da / 2.0),
       -math.sin(alpha) * math.sin(da / 2.0)],
      [math.sin(alpha) * math.sin(da / 2.0),
       math.cos(da / 2.0) + 1j * math.cos(alpha) * math.sin(da / 2.0)]]))
    self.name.append('+w');
    self.mutation_partners.append(['+z', '-z', '-w']);
    self.anti_operator.append('-w');

    # operator 4 -w
    self.M.append(np.matrix([
      [math.cos(-da / 2.0) - 1j * math.cos(alpha) * math.sin(-da / 2.0),
       -math.sin(alpha) * math.sin(-da / 2.0)],
      [math.sin(alpha) * math.sin(-da / 2.0),
       math.cos(-da / 2.0) + 1j * math.cos(alpha) * math.sin(-da / 2.0)]]))
    self.name.append('-w');
    self.mutation_partners.append(['+z', '-z', '+w']);
    self.anti_operator.append('+w');


  def check_unitarity(self):
    # this function checks if all defined operators are unitary
    # in case one isn't unitary the program stops
    for k in range(len(self.M)):
      if (np.trace(self.M[k] * self.M[k].getH()) - 2 != 0):
        print "Operator " + self.name[k] + " (no. " + str(
          k) + ") isn't unitary!"
        exit()

  def determine_index_of_mutation_partners(self):
    # create a field for each operator with an array of possible other gates for the mutation step
    for k in range(len(self.M)):
      hlp = []
      for m in range(len(self.mutation_partners[k])):
        # go through all possible partners and find them among the operators
        for n in range(len(self.M)):
          if self.mutation_partners[k][m] is self.name[n]:
            hlp.append(n)
      self.mutation_partners_no.append(hlp)

  def determine_index_of_anti_operators(self):
    # determine the Anti operator index
    for k in range(len(self.M)):
      found_operator = False
      for n in range(len(self.M)):
        # go through all possible partners and find them among the operators
        if self.anti_operator[k] is self.name[n]:
          self.anti_operator_no.append(n);
          found_operator = True

      if found_operator == False:
        print "Couldn't find the anti-operator for operator " + self.name[
          k] + " (no " + str(k) + ")"

  def __str__(self):
    # just a test to play around
    hlpstr = ''
    for k in range(len(self.M)):
      hlpstr = hlpstr + self.name[k] + " " + str(
        self.anti_operator_no[k]) + "\n"

    return "Operator Class:\n" + hlpstr


def calc_fidelity(sequence, Op, Ugoal):
  # Op will be function that return operator matrix
  # Ugoal 2x2 unitary matrix
  # sequence = [1 2 3 4];
  # return = fidelity

  # example:
  # sequence = [1 4 2 4 5];
  # Uapprox = Op(1) * Op(4) * Op(2) * Op(4) * Op(5);

  # create identity matrix
  Uapprox = np.eye(len(Ugoal))

  for k in range(len(sequence)):
    Uapprox = Op.M[sequence[k]] * Uapprox

  # M.getH() returns the complex conjugate of self
  result = (1.0 / len(Ugoal)) * abs(np.trace(Ugoal * Uapprox.getH()))

  return result



