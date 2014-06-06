# -*- coding: utf-8 -*-
from manipulator import *
from opentuner.search import technique
import random
import math

class PSO(technique.SequentialSearchTechnique ):
    """ Particle Swarm Optimization """
    def __init__(self, crossover, N = 3, init_pop=None, *pargs, **kwargs):
       """
        crossover: name of crossover operator function
        """
        super(PSO, self).__init__(*pargs, **kwargs)
        self.crossover = crossover
        self.name = 'pso-'+crossover
        self.init_pop = init_pop
        self.N = N

    def main_generator(self):

        objective   = self.objective
        driver      = self.driver
        m = self.manipulator
        def config(cfg):
            return driver.get_configuration(cfg)
    
        population = self.init_pop
        if not population:
            population = [HybridParticle(m, self.crossover, omega=0.5) for i in range(self.N)]

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
    def __init__(self, m, crossover_choice, omega=1, phi_l=0.5, phi_g=0.5):

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
            # Position as a continuous value in [0,1]
            self.position[p.name]= random.random()
            

    def move(self, global_best):
        """
        Update parameter values using corresponding operators. 
        TODO: introduce operator choice map
        """
        m = self.manipulator
        #print "cfg length check:", len(self.velocity), len(self.position)
        for p in m.params:
            if p.is_permutation(): #TODO: ALL parameters that require probablistic intepretation
                if random.uniform(0,1)>self.omega:
                    if random.uniform(0,1)<self.phi_l:
                        # Select crossover operator
                        getattr(p, self.crossover_choice)(self.position, self.position, global_best, d=p.size/3)
                    else:
                        getattr(p, self.crossover_choice)(self.position, self.position, self.best, d=p.size/3)
            else:
                # Continuous representation regardless of param type
                v = self.velocity+(-self.phi_l-self.phi_g)*self.position+ self.best*self.phi_l+ global_best*self.phi_g
                self.position = min(max([self.position+v, 0]),1)

    def to_cfg(self):
        data = {}
        for p in self.manipulator.params:
            if p.is_permutation():
                data[p.name] = self.position[p.name]
            else:
                if p.is_continuous():
                     data[p.name] = p.xmin+(p.position[name]*(p.xmax-p.xmin))

                elif p.is_ordinal():
                     data[p.name] = to_ordinal(self.position[p.name], classes(p))
                else: 
                    raise Exception("Behavior undefined for parameter", p)


def to_ordinal(v, classes):
    """ Map a value v in range [0,1] to discrete ordinal classes"""
    k = len(classes)
    # Map position to discrete space
    n1 = k/(1+exp(-v))
    # Add Gaussian noise and round
    n2 = round(random.gauss(n1, sigma*(k-1)))
    n3 = min(k-1, max(n2, 0)) 
    return classes[n3] 

# Parameter property check. Alternative: put field values in each Parameter class. 
    
continuous_params = [FloatParameter]
ordinal_params = [BooleanParameter, IntegerParameter]
nominal_params = [SwitchParameter, EnumParameter]
discrete_params = ordinal_params+nominal_params
params1D = continuous_params +discrete_params
paramsND = [PermutationParameter]

def is_continuous(parameter):
    """ Returns True if parameter is one of the continuous parameters defined in continuous_params """
    return sum([isinstance(parameter, p) for p in continuous_params])>0

def is_ordinal(parameter):
    return sum([isinstance(parameter, p) for p in ordinal_params])>0

def is_nomial(parameter):
    return sum([isinstance(parameter, p) for p in nominal_params])>0

def is_discrete(parameter):
    return (is_nomial(parameter) or is_ordinal(parameter))

technique.register(PSO(crossover = 'OX3'))
technique.register(PSO(crossover = 'OX1'))
technique.register(PSO(crossover = 'PMX'))
technique.register(PSO(crossover = 'PX'))
technique.register(PSO(crossover = 'CX'))
