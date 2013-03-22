from opentuner.resultsdb.models import *

class DriverBase(object):
  '''
  shared base class between MeasurementDriver and SearchDriver
  '''
  def __init__(self,
               session,
               tuning_run,
               objective,
               tuning_run_main,
               args,
               **kwargs):
    self.args            = args
    self.objective       = objective
    self.session         = session
    self.tuning_run_main = tuning_run_main
    self.tuning_run      = tuning_run

  def results_query(self,
                    generation = None,
                    objective_ordered = False,
                    config = None):
    q = self.session.query(Result)

    if config:
      q = q.filter_by(configuration = config)

    subq = (self.session.query(DesiredResult.result_id)
           .filter_by(tuning_run = self.tuning_run))
    if generation is not None:
      subq = subq.filter_by(generation = generation)
    q = q.filter(Result.id.in_(subq.subquery()))

    if objective_ordered:
      q = self.objective.result_order_by(q)

    return q

