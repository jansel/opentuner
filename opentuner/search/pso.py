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
#        m = PSOmanipulator(self.crossover, self.manipulator.params)
        m = self.manipulator
        def config(cfg):
            return driver.get_configuration(cfg)
    
        population = self.init_pop
        if not population:
            population = [HybridParticle(m, self.crossover, omega=0.5) for i in range(self.N)]

        for p in population:
            yield driver.get_configuration(p.position)
            
        while True:
            # For each particle
            for particle in population:
                g = driver.best_result.configuration.data
                old=m.copy(particle.position)
                particle.move(g)
    # send out for measurement
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
			# Probablistic update: currently only permutation
			if p.is_permutation():
				self.velocity=None
				self.position=None
			# Deterministc update
				# Continuous
			

				# Discrete: need mapping



            self.velocity[p.name]=0  
            p.continuous = False
            p.nominal = False
            p.ordinal = False
            for t in continous_params:
                if isinstance(p, t):
                    p.continous = True
            for t in nominal_params:
                if isinstance(p, t):
                    p.nominal = True
            for t in ordinal_params:
                if isinstance(p, t):
                    p.ordinal = True     


    def move(self, global_best):
        """
        Update parameter values using corresponding operators. 
        TODO: introduce operator choice map
        """
        m = self.manipulator
        #print "cfg length check:", len(self.velocity), len(self.position)
        for p in m.params:
            if p.is_permutation(): #or other parameter that requirs probablistic intepretation
                if random.uniform(0,1)>self.omega:
                    if random.uniform(0,1)<self.phi_l:
                        # Select crossover operator
                        getattr(p, self.crossover_choice)(self.position, self.position, global_best, d=p.size/3)
                    else:
                        getattr(p, self.crossover_choice)(self.position, self.position, self.best, d=p.size/3)
            else:
                # Continuous velocity representation regardless of param type
				v = self.velocity+(-self.phi_l-self.phi_g)*self.position+ self.best*self.phi_l+ global_best*self.phi_g

                if p.is_continuous():
                # If continuous, update position directly
                    p.weighted_sum(self.position, [self.position,self.velocity],[1,1])

                # Discrete parameters
                elif p.is_ordinal():        
                    k = p.nvalues()         
                    # Map position to discrete space
                    n1 = k/(1+exp(-self.position))
                    # Add Gaussian noise and round
                    n2 = round(random.gauss(c, sigma*(k-1)))
                    n3 = min(k, max(n2, 1)) 
                    p.set_value(n3, self.position)
                     
    #               print "local best", p._get(self.best), "position", p._get(self.position), "velocity", p._get(self.velocity)
                    print "local best", p._get(self.best), "global", p._get(global_best), "position", p._get(self.position), "velocity", p._get(self.velocity)
                else:
                    print "behavior undefined for", p

class Position(object):
    def __init__(self, manipulator):
        self.manipulator = manipulator
        self.dimensions = {}
        dscale = 100
        r = manipulator.random()
        for p in manipulator.params:
            if p.is_continuous():
                # Map discrete values to continuous domain
                self.dimensions[p.name]= random.uniform(*p.legal_range())
            else:
                self.dimensions[p.name] = None
"""
     def to_cfg(self):
         for p in self.manipulator.params:
             v = self.dimensions[p.name]
             if p.is_continuous():
                 v = self.discretize(v, *p.legal_range())
             p.set_value(cfg, v)

     def discretize(self, v, dmin, dmax, sigma=0.01):
         ''' Convert from continuous to discrete ordinal values based on method described by Veeramachaneni 2007 
             v: a continuous value
             dmin, dmax: min and max values in the discrete space
             sigma: variance introduced by gaussian noise
             return: dicrete value in range [dmin, dmax]
         '''
         M = dmax - dmin + 1
         m = round(math.gauss(M/(1+math.exp(-v)), sigma))
         return max(dmin, min(dmax, m))
"""         
class PSOmanipulator(ConfigurationManipulator):
    def __init__(self, crossover, *pargs, **kwargs):
        super(PSOmanipulator, self).__init__(*pargs, **kwargs)
        self.crossover_choice = crossover

    def mix(self, dest, cfg1, cfg2):
        params = self.params
        random.shuffle(params)
        params[0].randomize(dest)
        for p in self.params:
            if p.is_permutation() and p.size>6:
                # Select crossover operator
                getattr(p, self.crossover_choice)(dest, cfg1, cfg2, d=p.size/3)
            elif p.is_numeric():
                p.set_linear(dest, cfg1, cfg2)
    
    def scale(self, dcfg, k):
        """ Scale a velocity by k """
        new = self.copy(dcfg)
        for p in self.params:
            if isinstance(p, manipulator.PermutationParameter):                   
                new[p.name]=p.scale_swaps(new[p.name], k)
            else:
                p.scale(new, k)
        return new

    def split(self, dcfg, k):
        new1 = self.copy(dcfg)
        new2 = self.copy(dcfg)
        for p in self.params:
            if isinstance(p, manipulator.PermutationParameter):                   
                new1[p.name], new2[p.name]=p.split_swaps(dcfg[p.name], k)
            else:
                pass
        return new1, new2           

    def sum_v(self, *vs):
        """ Return the sum of a list of velocities """
        vsum= {}
        for p in self.params:
            if isinstance(p, manipulator.PermutationParameter):
                vsum[p.name] = p.sum_swaps(*[v[p.name] for v in vs])
            else:
                p.sum(vsum, *vs)       
        return vsum
        
        

    def add_v(self, cfg, v):
        """ Add a velocity to the position """
        new = self.copy(cfg)
        for p in self.params:
            if isinstance(p, manipulator.PermutationParameter):
                p.apply_swaps(v[p.name], new)
            else:
                p.sum(new, v, cfg)

        return new
        

    def crossover(self, dest, cfg1, cfg2):
        for p in self.params:
            if p.is_permutation():
                # Select crossover operator
                getattr(p, self.crossover_choice)(dest, cfg1, cfg2, d=p.size/3)
         

    
continous_params = [FloatParameter]
ordinal_params = [BooleanParameter, IntegerParameter]
nominal_params = [SwitchParameter, EnumParameter]
discrete_params = ordinal_params+nominal_params

params1D = continous_params+discrete_params
paramsND = [PermutationParameter, ArrayParameter]


technique.register(PSO(crossover = 'OX3'))
technique.register(PSO(crossover = 'OX1'))
technique.register(PSO(crossover = 'PMX'))
technique.register(PSO(crossover = 'PX'))
technique.register(PSO(crossover = 'CX'))
