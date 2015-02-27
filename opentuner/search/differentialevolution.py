import random
import time
import logging
from fn import _
from technique import register
from technique import SearchTechnique

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)


class PopulationMember(object):
  def __init__(self, config, submitted=True):
    self.config = config
    self.submitted = submitted
    self.timestamp = time.time()
    self.candidate_replacement = None

  def touch(self):
    self.timestamp = time.time()


class DifferentialEvolution(SearchTechnique):
  """
  based on http://cci.lbl.gov/cctbx_sources/scitbx/differential_evolution.py
  """

  def __init__(self,
               population_size=30,
               cr=0.9,  # crossover rate
               n_cross=1,  # force at least 1 to crossover
               information_sharing=1,  # number token sharing pop members
               duplicate_retries=5,  # how many times to retry on duplicate
               *pargs, **kwargs):

    self.population_size = population_size
    self.cr = cr
    self.n_cross = n_cross
    self.information_sharing = information_sharing
    self.population = None
    self.duplicate_retries = duplicate_retries
    self.limit = None
    super(DifferentialEvolution, self).__init__(*pargs, **kwargs)

  @classmethod
  def get_hyper_parameters(cls):
    return ['population_size', 'cr', 'n_cross', 'information_sharing']

  def initial_population(self):
    self.population = [PopulationMember(
        self.driver.get_configuration(
            self.manipulator.random()), submitted=False)
        for z in xrange(self.population_size)]

  def oldest_pop_member(self):
    # since tests are run in parallel, exclude things with a replacement pending
    pop_without_replacements = filter(lambda x: x.candidate_replacement is None,
                                      self.population)
    if not pop_without_replacements:
      # everything has a pending replacement
      return None
    pop_without_replacements.sort(key=_.timestamp)
    return pop_without_replacements[0]

  def desired_configuration(self):
    """
    return a cfg that we should test,
    """
    if not self.population:
      # first time called
      self.initial_population()

    # make sure initial population is completely submitted
    for p in self.population:
      if not p.submitted:
        p.submitted = True
        if p is self.population[-1]:
          log.info('initial population testing done')
        return p.config

    # pp is member of population to be replaced
    oldest_pop_member = self.oldest_pop_member()
    if not oldest_pop_member:
      return None

    config = None
    for retry in xrange(self.duplicate_retries):
      config = self.driver.get_configuration(
          self.create_new_configuration(oldest_pop_member))
      if not self.driver.has_results(config):
        break
      # new configuration would have been a duplicate, try again

    oldest_pop_member.touch()  # move to back of the line for next replacement
    oldest_pop_member.candidate_replacement = config
    self.limit = self.driver.objective.limit_from_config(
        oldest_pop_member.config)
    return oldest_pop_member.candidate_replacement

  def create_new_configuration(self, parent_pop_member):
    cfg = self.manipulator.copy(parent_pop_member.config.data)
    cfg_params = self.manipulator.proxy(cfg)

    # pick 3 random parents, not pp
    shuffled_pop = list(set(self.population) - set([parent_pop_member]))

    # share information with other techniques
    if self.driver.best_result:
      shuffled_pop += ([PopulationMember(self.driver.best_result.configuration)]
                       * self.information_sharing)

    random.shuffle(shuffled_pop)
    x1, x2, x3 = map(_.config.data, shuffled_pop[0:3])

    use_f = random.random() / 2.0 + 0.5

    params = self.manipulator.param_names(cfg, x1, x2, x3)
    random.shuffle(params)
    for i, k in enumerate(params):
      if i < self.n_cross or random.random() < self.cr:
        # cfg = x1 + use_f*(x2 - x3)
        cfg_params[k].op4_set_linear(x1, x2, x3, 1.0, use_f, -use_f)

    return cfg

  def handle_requested_result(self, result):
    """called when new results are added"""
    for p in self.population:
      if p.candidate_replacement == result.configuration:
        if self.objective.lt(p.candidate_replacement, p.config):
          # candidate replacement was better, replace it!
          p.config = p.candidate_replacement
          log.info('better point')
        p.candidate_replacement = None


class DifferentialEvolutionAlt(DifferentialEvolution):
  def __init__(self, cr=0.2, **kwargs):
    kwargs['cr'] = cr
    super(DifferentialEvolutionAlt, self).__init__(**kwargs)


register(DifferentialEvolution())
register(DifferentialEvolutionAlt())
register(DifferentialEvolution(population_size=100, cr=0.2,
                               name='DifferentialEvolution_20_100'))


