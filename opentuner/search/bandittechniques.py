import abc
import sys
import logging
import math
import random
from collections import deque, defaultdict
from fn import _

from .metatechniques import MetaSearchTechnique
from .technique import register

log = logging.getLogger(__name__)

class BanditQueue(object):
  def __init__(self, keys, C=0.05, window=500, **kwargs):
    '''
    C is exploration/exploitation tradeoff
    window is how long to remember past results
    '''
    super(BanditQueue, self).__init__(**kwargs)
    self.C = C
    self.history = deque()
    self.keys = keys
    self.use_counts = dict(((k, 0) for k in keys))
    self.window = window

  @abc.abstractmethod
  def exploitation_term(self, key):
    '''
    value 0 to 1.0 to represent quality of technique
    '''
    return 0.0

  def exploration_term(self, key):
    '''
    value represent how unsure we are (optimal bandit solution)
    '''
    if self.use_counts[key] > 0:
      return math.sqrt( (2.0 * math.log(len(self.history), 2.0))
                      / self.use_counts[key])
    else:
      return float('inf')

  def bandit_score(self, key):
    return (self.exploitation_term(key) +
            self.C * self.exploration_term(key))

  def ordered_keys(self):
    '''select the next technique to use'''

    keys = list(self.keys)
    random.shuffle(keys) #break ties randomly
    keys.sort(key=self.bandit_score)

    if log.isEnabledFor(logging.DEBUG) and (self.request_count % 1000) == 0:
      log.debug(str([
          (t.name, self.exploitation_term(t), self.C*self.exploration_term(t))
          for t in keys
        ]))

    return reversed(keys)

  def on_result(self, key, value):
    self.history.append((key, value))
    self.on_push_history(key, value)
    if len(self.history) > self.window:
      self.on_pop_history(*self.history.popleft())

  def on_push_history(self, key, value):
    self.use_counts[key] += 1

  def on_pop_history(self, key, value):
    self.use_counts[key] -= 1

class AUCBanditQueue(BanditQueue):
  '''
  Area Under the Receiving Operator Curve (AUC) credit assignment

  See:
  Comparison-based adaptive strategy selection with bandits in differential
  evolution. Fialho et al.
  '''

  def __init__(self, *args, **kwargs):
    super(AUCBanditQueue, self).__init__(*args, **kwargs)
    self.debug = kwargs.get('debug', False)
    self.auc_sum   = dict(((t, 0) for t in self.keys))
    self.auc_decay = dict(((t, 0) for t in self.keys))

  def exploitation_term_slow(self, key):
    '''
    value 0 to 1.0 to represent quality of key

    computes the area under the curve where finding a new
    global best results in adding 1 to a cumulative total
    '''
    score = 0.0
    pos = 0
    for t, value in self.history:
      if t is key:
        pos += 1
        if value:
          score += pos
    if pos:
      return score * 2.0 / (pos * (pos + 1.0))
    else:
      return 0.0

  def exploitation_term_fast(self, key):
    '''
    value 0 to 1.0 to represent quality of key

    optimized O(1) implementation exploitation_term_slow()
    '''
    score = self.auc_sum[key]
    pos = self.use_counts[key]
    if pos:
      return score * 2.0 / (pos * (pos + 1.0))
    else:
      return 0.0

  def exploitation_term(self, key):
    v1 = self.exploitation_term_fast(key)
    if self.debug:
      v2 = self.exploitation_term_slow(key)
      assert v1 == v2
    return v1

  def on_push_history(self, key, value):
    super(AUCBanditQueue, self).on_push_history(key, value)
    if value:
      self.auc_sum[key] += self.use_counts[key]
      self.auc_decay[key] += 1

  def on_pop_history(self, key, value):
    super(AUCBanditQueue, self).on_pop_history(key, value)
    self.auc_sum[key] -= self.auc_decay[key]
    if value:
      self.auc_decay[key] -= 1



class AUCBanditMetaTechnique(MetaSearchTechnique):
  def __init__(self, techniques, bandit_kwargs=dict(), **kwargs):
    super(AUCBanditMetaTechnique, self).__init__(techniques, **kwargs)
    self.bandit = AUCBanditQueue([t.name for t in techniques], **bandit_kwargs)
    self.name_to_technique = dict(((t.name, t) for t in self.techniques))

  def select_technique_order(self):
    '''select the next technique to use'''
    return (self.name_to_technique[k] for k in self.bandit.ordered_keys())

  def on_technique_result(self, technique, result):
    self.bandit.on_result(technique.name, result.was_new_best)

import evolutionarytechniques
import differentialevolution
import simplextechniques

register(
    AUCBanditMetaTechnique([
      differentialevolution.DifferentialEvolution(),
      simplextechniques.MultiNelderMead(),
      simplextechniques.MultiTorczon(),
      evolutionarytechniques.GreedyMutation()]))


