from __future__ import absolute_import
from __future__ import division

import random

from .technique import SequentialSearchTechnique
from .technique import register


class BinaryGA(SequentialSearchTechnique):
    def __init__(self,
                 population=200,
                 tournament=5,
                 mutate=2,
                 sharing=1,
                 **kwargs):
        super(BinaryGA, self).__init__(**kwargs)
        self.population_size = population
        self.tournament_size = tournament
        self.mutate_count = mutate
        self.sharing = sharing
        self.population = None

    def seed_config(self):
        member = self.driver.get_configuration(self.manipulator.random())
        self.yield_nonblocking(member)
        return member

    def select_parent(self):
        best = self.driver.best_result.configuration
        sources = self.population + [best] * self.sharing
        parent = random.choice(sources)
        for _ in range(self.tournament_size - 1):
            other = random.choice(sources)
            if self.objective.lt(other, parent):
                parent = other
        return parent

    def create_offspring(self):
        cfg = self.manipulator.copy(self.select_parent().data)
        other_parent = self.select_parent().data
        params = self.manipulator.parameters(cfg)

        # half the values from other parent
        for param in random.sample(params, k=len(params) // 2):
            param.copy_value(other_parent, cfg)

        # some mutation
        for param in random.sample(params, k=self.mutate_count):
            param.op1_randomize(cfg)

        # submit it for testing
        member = self.driver.get_configuration(cfg)
        self.yield_nonblocking(member)
        return member

    def main_generator(self):
        self.population = [self.seed_config() for _ in range(self.population_size)]
        yield None  # wait for initial population

        while True:
            self.population = [self.create_offspring() for _ in range(self.population_size)]
            yield None  # wait for next population


register(BinaryGA())
