# -*- coding: utf-8 -*-
# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab autoindent smarttab
from manipulator import *
from opentuner.search import technique
import random
import math

class PSO(technique.SequentialSearchTechnique ):
  """ Particle Swarm Optimization """
  def __init__(self, crossover, N = 30, init_pop=None, *pargs, **kwargs):
    """
    crossover: name of crossover operator function
    """
    super(PSO, self).__init__(*pargs, **kwargs)
    self.crossover = crossover
    self.name = 'pso-'+crossover.replace("op3_cross_","")
    self.init_pop = init_pop
    self.N = N

  def main_generator(self):

    objective   = self.objective
    driver    = self.driver
    m = self.manipulator
    def config(cfg):
      return driver.get_configuration(cfg)
  
    population = self.init_pop
    if not population:
      population = [HybridParticle(m, self.crossover) for i in range(self.N)]

    for p in population:
      yield driver.get_configuration(p.position)

    while True:
      for particle in population:
        g = driver.best_result.configuration.data
        old=m.copy(particle.position)
        particle.move(g)
        yield config(particle.position)
        # update individual best
        if objective.lt(config(particle.position), config(particle.best)):
          particle.best = particle.position

class HybridParticle(object):
  def __init__(self, m, crossover_choice, omega=0.5, phi_l=0.5, phi_g=0.5):

    """
    m: a configuraiton manipulator
    omega: influence of the particle's last velocity, a float in range [0,1] ; omega=1 means even speed
    phi_l: influence of the particle's distance to its historial best position, a float in range [0,1]
    phi_g: influence of the particle's distance to the global best position, a float in range [0,1]
    """

    self.manipulator = m
    self.position = self.manipulator.random()   
    self.best = self.position
    self.omega = omega
    self.phi_l = phi_l
    self.phi_g = phi_g
    self.crossover_choice = crossover_choice
    self.velocity = {}
    for p in self.manipulator.params:
      # Velocity as a continous value
      self.velocity[p.name]=0  

  def move(self, global_best):
    """
    Update parameter values using corresponding operators. 
    TODO: introduce operator choice map
    """
    m = self.manipulator
    for p in m.params:
      self.velocity[p.name] = p.op3_swarm(self.position, global_best, self.best, c=self.omega, c1=self.phi_g, c2=self.phi_l, xchoice=self.crossover_choice, velocity=self.velocity[p.name])


technique.register(PSO(crossover = 'op3_cross_OX3'))
technique.register(PSO(crossover = 'op3_cross_OX1'))
technique.register(PSO(crossover = 'op3_cross_PMX'))
technique.register(PSO(crossover = 'op3_cross_PX'))
technique.register(PSO(crossover = 'op3_cross_CX'))
