import logging
import time
from fn import _

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


class LogDisplayPlugin(SearchPlugin):
  def __init__(self, display_period=10):
    super(LogDisplayPlugin, self).__init__()
    self.last  = time.time()
    self.start = time.time()
    self.display_period = display_period

  def display(self, driver, t=None):
    if not t:
      t = time.time()
    count = driver.results_query().count()
    try:
      best = driver.results_query(objective_ordered = True).limit(1).one()
    except KeyboardInterrupt: raise
    except:
      log.warning("no results yet")
      return
    requestor = ','.join(map(_.requestor, best.desired_results))
    log.info("[%6.0f] test=%d, best time=%.4f acc=%.4f, found by %s",
             t-self.start,
             count,
             best.time,
             best.accuracy if best.accuracy is not None else float('NaN'),
             requestor,
             )

  def after_generation(self, driver):
    t = time.time()
    if t - self.display_period > self.last:
      # call display every 10 seconds
      self.last = t
      self.display(driver, t)

  def after_main(self, driver):
    self.display(driver)

def get_enabled(args):
  return [LogDisplayPlugin()]



