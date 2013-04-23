import abc
import sys
import logging
import math
import random
from collections import deque, defaultdict
from fn import _

from .metatechniques import MetaSearchTechnique

log = logging.getLogger(__name__)

class BanditMetaTechnique(MetaSearchTechnique):
  def __init__(self, techniques, C=0.5, window=100, **kwargs):
    '''
    C is exploration/exploitation tradeoff
    window is how long to remember past results
    '''
    super(BanditMetaTechnique, self).__init__(techniques, **kwargs)
    self.window = window
    self.C = C
    self.history = deque(maxlen=window) #will drop >window elements
    self.technique_use_counts = None

  @abc.abstractmethod
  def exploitation_term(self, technique):
    '''
    value 0 to 1.0 to represent quality of technique
    '''
    return 0.0

  def exploration_term(self, technique):
    '''
    value represent how unsure we are (optimal bandit solution)
    '''
    if technique in self.technique_use_counts:
      return math.sqrt( (2.0 * math.log(len(self.history), 2.0))
                      / self.technique_use_counts[technique])
    else:
      return float('inf')

  def bandit_score(self, technique):
    return (self.exploitation_term(technique) +
            self.C * self.exploration_term(technique))

  def select_technique_order(self):
    '''select the next technique to use'''

    if len(self.techniques) <= 1:
      # no choices
      return self.techniques

    # refresh technique_use_counts
    self.technique_use_counts = defaultdict(int)
    for t, result in self.history:
      self.technique_use_counts[t] += 1

    techniques = list(self.techniques)
    random.shuffle(techniques) #break ties randomly
    techniques.sort(key=self.bandit_score)
    return reversed(techniques)

  def on_technique_result(self, technique, result):
    self.history.append((technique, result))

class AUCBanditMetaTechnique(BanditMetaTechnique):
  '''
  Area Under the Receiving Operator Curve (AUC) credit assignment

  See:
  Comparison-based adaptive strategy selection with bandits in differential
  evolution. Fialho et al.
  '''
  def exploitation_term(self, technique):
    '''
    value 0 to 1.0 to represent quality of technique
    '''
    score = 0.0
    pos = 0
    for t, result in self.history:
      pos += 1
      if t is technique and result.was_new_best:
        score += pos
    if pos:
      return score * 2.0 / (pos * (pos + 1.0))
    else:
      return 0.0

