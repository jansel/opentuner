import numpy as np
import math
import random


def generate_random_Ugoal_HARD(N, **kwargs):
  # N is the length of random matrix multiplication yielding Ugoal
  # N ~ 100 should be enough
  # This method is hard because it creates Ugoal over the whole space
  # Ugoal 2x2 unitary matrix

  # create identity matrix
  Ugoal = np.eye(2)

  # create all N random angles in 2*pi*[0,1)
  seq_angle = 2.0 * math.pi * np.random.rand(1, N)

  # determine random operator
  help2 = np.random.randint(3, size=(1, N))

  for k in range(N):
    hlp = seq_angle[0][k];
    if help2[0][k] == 0:
      Ugoal = X_Mat(hlp) * Ugoal
    elif help2[0][k] == 1:
      Ugoal = Y_Mat(hlp) * Ugoal
    else:
      Ugoal = Z_Mat(hlp) * Ugoal

  return Ugoal


def generate_random_Ugoal_EASY(N, alpha):
  # N is the length of random matrix multiplication yielding Ugoal
  # N ~ 100 should be enough
  # alpha is the used angle between rotation axes
  # This method is easy because it creates Ugoal over the whole space
  # Ugoal 2x2 unitary matrix

  # create identity matrix
  Ugoal = np.eye(2)

  # create all N random angles in 2*pi*[0,1)
  seq_angle = 2.0 * math.pi * np.random.rand(1, N)

  # determine random operator
  help2 = np.random.randint(2, size=(1, N))

  for k in range(N):
    hlp = seq_angle[0][k];
    if help2[0][k] == 0:
      Ugoal = Z_Mat(hlp) * Ugoal
    else:
      Ugoal = W_Mat(hlp, alpha) * Ugoal

  return Ugoal


def generate_random_Ugoal_RANDOM(**kwargs):
  # Random guess with the following parametrization for U
  # U = @(q1, q2, q3) [
  #				[ cos(q1)*exp( i*q2 ), sin(q1)*exp( i*q3 )];
  #                [-sin(q1)*exp(-i*q3 ), cos(q1)*exp(-i*q2 )]
  #                    ];

  # create random angles
  q1 = random.uniform(0.0, 0.5 * math.pi)
  q2 = random.uniform(0.0, 2.0 * math.pi)
  q3 = random.uniform(0.0, 2.0 * math.pi)

  return np.matrix([
    [math.cos(q1) * my_cexp(q2), math.sin(q1) * my_cexp(q3)],
    [-math.sin(q1) * my_cexp(-q3), math.cos(q1) * my_cexp(-q2)]])


def my_cexp(x):
  return math.cos(x) + 1j * math.sin(x)


def X_Mat(a):
  return np.matrix([[math.cos(a / 2.0), -1j * math.sin(a / 2.0)],
                    [-1j * math.sin(a / 2.0), math.cos(a / 2.0)]])


def Y_Mat(a):
  return np.matrix([[math.cos(a / 2.0), -math.sin(a / 2.0)],
                    [math.sin(a / 2.0), math.cos(a / 2.0)]])


def Z_Mat(a):
  return np.matrix([[math.cos(-a / 2.0) + 1j * math.sin(-a / 2.0), 0],
                    [0, math.cos(a / 2.0) + 1j * math.sin(a / 2.0)]])


def W_Mat(a, alpha):
  return np.matrix([[math.cos(a / 2) - 1j * math.cos(alpha) * math.sin(a / 2.0),
                     -math.sin(a / 2.0) * math.sin(alpha)],
                    [math.sin(a / 2.0) * math.sin(alpha),
                     math.cos(a / 2.0) + 1j * math.cos(alpha) * math.sin(
                       a / 2.0)]])
