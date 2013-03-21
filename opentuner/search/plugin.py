import logging
import time
import tempfile
import sys
import abc
from datetime import datetime
from fn import _
from sqlalchemy.orm.exc import NoResultFound

from opentuner.resultsdb.models import Result

log = logging.getLogger(__name__)

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
   #requestor = ','.join(map(_.requestor, best.desired_results))
   #log.info("[%6.0f] tests=%d, best time=%.4f acc=%.4f, found by %s",
   #         t-self.start,
   #         count,
   #         best.time,
   #         best.accuracy if best.accuracy is not None else float('NaN'),
   #         requestor,
   #         )
    log.info("[%6.0f] tests=%d, best time=%.4f acc=%.4f",
             t-self.start,
             count,
             best.time,
             best.accuracy if best.accuracy is not None else float('NaN'),
             )

class GnuplotDisplayPlugin(DisplayPlugin):
  def __init__(self, *args, **kwargs):
    super(GnuplotDisplayPlugin, self).__init__(*args, **kwargs)
    self.last_result_date = None
    self.last_best = float('inf')
    self.start_date = datetime.now()
    #self.out = tempfile.NamedTemporaryFile(suffix=".dat")
    #log.info("gnuplot data file %s", self.out.name)
    self.out = open("/tmp/livedisplay.dat", "w")
    self.details = open("/tmp/livedisplaydetails.dat", "w")

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
      else:
        print >>self.details, \
            (result.collection_date - self.start_date).total_seconds(), \
            result.time
        self.details.flush()

def get_enabled(args):
  return [GnuplotDisplayPlugin(),
          LogDisplayPlugin(1)]



