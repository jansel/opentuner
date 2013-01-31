import logging

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
  def after_generation(self, driver):
    result = driver.results_query(objective_ordered = True).limit(1).one()
    log.info("generation %d, best result time=%.4f, accuracy=%.4f, found in generation %d",
             driver.generation,
             result.time,
             result.accuracy if result.accuracy is not None else float('NaN'),
             result.desired_results[0].generation,
             )


def get_enabled(args):
  return [LogDisplayPlugin()]



