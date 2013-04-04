import abc
import argparse
import logging
import sys
import tempfile
import time

from datetime import datetime
from fn import _
from sqlalchemy.orm.exc import NoResultFound

from opentuner.resultsdb.models import Result

log = logging.getLogger(__name__)
display_log = logging.getLogger(__name__ + ".DisplayPlugin")

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--results-log',
    help="file to store log of the best configuration times")
argparser.add_argument('--results-log-details',
    help="file to store log of the non-best configuration times")
argparser.add_argument('--quiet', action='store_true',
    help="print less information")


class SearchPlugin(object):
  @property
  def priority(self):
    '''control order the plugin hooks gets run in, lower runs first'''
    return 0

  def set_driver(self, driver):
    '''called before all other methods'''
    self.driver = driver

  def before_main(self): pass
  def after_main(self):  pass

  def before_techniques(self): pass
  def after_techniques(self):  pass

  def before_results_wait(self): pass
  def after_results_wait(self):  pass

  def on_result(self, result):
    '''
    called once for every new result
    '''
    pass

  def on_result_for_technique(self, result, technique):
    '''
    called right before a result is given to a technique
    (result may be requested by multiple techniques)
    '''
    pass

  def on_new_best_result(self, result):
    '''
    called whenever the global best result changes
    '''
    pass

class DisplayPlugin(SearchPlugin):
  __metaclass__ = abc.ABCMeta
  def __init__(self, display_period=5):
    super(DisplayPlugin, self).__init__()
    self.last  = time.time()
    self.start = time.time()
    self.display_period = display_period

  def after_results_wait(self):
    t = time.time()
    if t - self.display_period > self.last:
      # call display every 5 seconds
      self.last = t
      self.display(t)

  def after_main(self):
    self.display()

  @abc.abstractmethod
  def display(self, t=None):
    pass


class LogDisplayPlugin(DisplayPlugin):
  def display(self, t=None):
    if not t:
      t = time.time()
    count = self.driver.results_query().count()
    try:
      best = self.driver.results_query(objective_ordered = True).limit(1).one()
    except NoResultFound:
      log.warning("no results yet")
      return
    requestor = ','.join(map(_.requestor, best.desired_results))
    display_log.info("[%6.0f] tests=%d, best time=%.4f acc=%.4f, found by %s",
                     t-self.start,
                     count,
                     best.time,
                     best.accuracy if best.accuracy is not None else float('NaN'),
                     requestor,
                     )

class FileDisplayPlugin(SearchPlugin):
  def __init__(self, out, details,  *args, **kwargs):
    super(FileDisplayPlugin, self).__init__(*args, **kwargs)
    self.last_best = float('inf')
    self.start_date = datetime.now()
    self.out = open(out, "w")
    if out == details:
      self.details = self.out
    elif details:
      self.details = open(details, "w")
    else:
      self.details = None

  def on_result(self, result):
    if result.time < self.last_best:
      self.last_best = result.time
      print >>self.out, \
          (result.collection_date - self.start_date).total_seconds(), \
          result.time
      self.out.flush()
    elif self.details:
      print >>self.details, \
          (result.collection_date - self.start_date).total_seconds(), \
          result.time
      self.details.flush()

def get_enabled(args):
  plugins = []
  if not args.quiet:
    plugins.append(LogDisplayPlugin())
  if args.results_log:
    plugins.append(FileDisplayPlugin(args.results_log, args.results_log_details))
  return plugins



