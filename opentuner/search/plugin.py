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

  def before_main(self, driver):
    pass

  def after_main(self, driver):
    pass

  def before_generation(self, driver):
    pass

  def after_generation(self, driver):
    pass

  def before_techniques(self, driver):
    pass

  def after_techniques(self, driver):
    pass

  def before_result_wait(self, driver):
    pass

  def after_result_wait(self, driver):
    pass

  def before_result_handlers(self, driver, result, desired_results):
    pass

  def after_result_handlers(self, driver, result, desired_results):
    pass


class DisplayPlugin(SearchPlugin):
  __metaclass__ = abc.ABCMeta
  def __init__(self, display_period=5):
    super(DisplayPlugin, self).__init__()
    self.last  = time.time()
    self.start = time.time()
    self.display_period = display_period

  def after_generation(self, driver):
    t = time.time()
    if t - self.display_period > self.last:
      # call display every 10 seconds
      self.last = t
      self.display(driver, t)

  def after_main(self, driver):
    self.display(driver)

  @abc.abstractmethod
  def display(self, driver, t=None):
    pass

class LogDisplayPlugin(DisplayPlugin):
  def display(self, driver, t=None):
    if not t:
      t = time.time()
    count = driver.results_query().count()
    try:
      best = driver.results_query(objective_ordered = True).limit(1).one()
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

class FileDisplayPlugin(DisplayPlugin):
  def __init__(self, out, details,  *args, **kwargs):
    super(FileDisplayPlugin, self).__init__(*args, **kwargs)
    self.last_result_date = None
    self.last_best = float('inf')
    self.start_date = datetime.now()
    self.out = open(log, "w")
    if out == details:
      self.details = self.out
    elif details:
      self.details = open(details, "w")
    else:
      self.details = None

  def display(self, driver, t=None):
    q = driver.results_query()
    if self.last_result_date:
      q = q.filter(Result.collection_date > self.last_result_date)
    q = q.order_by(Result.collection_date)
    for result in q:
      self.last_result_date = result.collection_date
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



