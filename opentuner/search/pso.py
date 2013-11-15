# -*- coding: utf-8 -*-
from opentuner.search import technique, manipulator
import random

N=10

class PSO(technique.SequentialSearchTechnique ):
    """ Particle Swarm Optimization """
    def __init__(self, crossover, *pargs, **kwargs):
        """
        crossover: name of crossover operator function
        """
        super(PSO, self).__init__(*pargs, **kwargs)
        self.crossover = crossover
        self.name = 'pso-'+crossover
        
    def main_generator(self):
        
        objective   = self.objective
        driver      = self.driver
        m = PSOmanipulator(self.crossover, self.manipulator.params)
        def config(cfg):
            return driver.get_configuration(cfg)

        population = [DiscreteParticle(m, omega=0.5) for i in range(N)]
        for p in population:
            yield driver.get_configuration(p.position)
            
        while True:
            # For each particle
            for particle in population:
                g = driver.best_result.configuration.data
		old=m.copy(particle.position)
                particle.move(g)
                print ((old==particle.position) or (g==particle.position))
		# send out for measurement
                yield config(particle.position)
                # update individual best
                if objective.lt(config(particle.position), config(particle.best)):
                    particle.best = particle.position
                           
 


class Particle(object):     # should inherit from/link to ConfigurationManipulator? 
    def __init__(self, m, omega=1, phi_l=0.5, phi_g=0.5):
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
        
    def __str__(self):
        return 'V:'+str(self.velocity)+'\tP:'+str(self.position)

    def move(self, global_best):
        pass

class ContinuousParticle(Particle):     # should inherit from/link to ConfigurationManipulator? 
    def __init__(self, *args):
        super(ContinuousParticle, self).__init__(*args)      
        self.velocity = m.difference(m.random(), m.random())   # velocity domain; initial value
        
    def move(self, global_best):
        """ move the particle towards its historical best and global best """
        m = self.manipulator
        v = m.sum_v(
            m.scale(self.velocity,random.uniform(0,self.omega)),
            m.scale(m.difference(self.best, self.position),random.uniform(0,self.phi_l)),
            m.scale(m.difference(global_best, self.position),random.uniform(0,self.phi_g))
                  )
        self.velocity = v
        self.position = m.add_v(self.position, v)


class DiscreteParticle(Particle):
    def move(self, global_best):
        m = self.manipulator
        # Decide if crossover happens
        if random.uniform(0,1)<self.omega:
            return
        else:
	    current = m.copy(self.position)
            if random.uniform(0,1)<self.phi_l:
                 m.crossover(self.position, current, global_best)
            else:
                 m.crossover(self.position, current, self.best)
        
class HybridParticle(Particle):
    def move(self, global_best):
        m = self.manipulator
        if random.uniform(0,1)<self.omega:
            return
        else:
            if random.uniform(0,1)<self.phi_l:
                 m.mix(self.position, self.position, global_best)
            else:
                 m.mix(self.position, self.position, self.best)
        
         
class ParticleIII(Particle):
    """
    At each step, randomly chooses one motion out of:
    (i) continuing previous motion
    (ii) moving towards local best
    (iii) moving towards global best
    """

    def move(self, global_best):
        m = self.manipulator
        # Randomly choose one direction instead of combining all three
        vs= [
            m.scale(self.velocity,random.uniform(0,self.omega)),
            m.scale(m.difference(self.best, self.position),random.uniform(0,self.phi_l)),
            m.scale(m.difference(global_best, self.position),random.uniform(0,self.phi_g))
            ]
                
        choice = random.randint(0,2)
        self.velocity = vs[choice]
        self.position = m.add_v(self.position, vs[choice])
        
        
class ParticleIV(Particle):
    """
    Similar to ParticleIII except that velocity can only be a subsequence of the swap sequence
    velocity, and the unused portion of the swap sequence is stored as the particle's velocity
    """
    def move(self, global_best):
        m = self.manipulator
        # Randomly choose one direction instead of combining all three
        vs= [
            m.split(self.velocity,random.uniform(0,self.omega)),
            m.split(m.difference(self.best, self.position),random.uniform(0,self.phi_l)),
            m.split(m.difference(global_best, self.position),random.uniform(0,self.phi_g))
            ]
                
        choice = random.randint(0,2)
        self.velocity = vs[choice][1]
        self.position = m.add_v(self.position, vs[choice][0])
        
    
class PSOmanipulator(manipulator.ConfigurationManipulator):
    def __init__(self, crossover, *pargs, **kwargs):
        super(PSOmanipulator, self).__init__(*pargs, **kwargs)
        self.crossover_choice = crossover

    def difference(self, cfg1, cfg2):
        """ Return the difference of two positions i.e. velocity """
        v = self.copy(cfg1)
        for p in self.params:
            if p.is_numeric():
                p.difference(v, cfg1, cfg2)
            else:
                pass

        return v
        

    def mix(sel, dest, cfg1, cfg2):
        params = self.params
        params = random.shuffle(params)
        for p in self.params:
            if p.is_permutation():
                # Select crossover operator
                getattr(p, self.crossover_choice)(dest, cfg1, cfg2, d=p.size/3)
            else:
                p.randomize(dest)
                break 
    
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
		getattr(p, self.crossover_choice)(dest, cfg1, cfg2, d=5)
         
                                

technique.register(PSO(crossover = 'OX3'))
technique.register(PSO(crossover = 'OX1'))
technique.register(PSO(crossover = 'PMX'))
technique.register(PSO(crossover = 'PX'))
technique.register(PSO(crossover = 'CX'))
