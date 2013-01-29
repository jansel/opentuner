import logging
import argparse
import hashlib
import math
from datetime import datetime, timedelta
from fn import _
from fn import Stream
from fn.iters import repeat
from collections import defaultdict

from opentuner import resultsdb
from opentuner.resultsdb.models import *

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--stats', action='store_true',
                       help="run in stats mode")
argparser.add_argument('--stats-quanta', type=float, default=10,
                       help="step size in seconds for binning with --stats")

def mean(vals): return sum(vals)/float(len(vals))

def variance(vals):
  avg = mean(vals)
  return mean(map((_ - avg) ** 2, vals))

def stddev(vals):
  return math.sqrt(variance(vals))

def hash_args(x):
  return hashlib.sha256(str(sorted(vars(x).items()))).hexdigest()[:20]

def run_name(tr):
  return tr.name + '_' + hash_args(tr.args)

class StatsMain(object):
  def __init__(self, measurement_interface, args):
    self.args = args
    if not args.database:
      args.database = 'sqlite://' #in memory
    self.engine, self.Session = resultsdb.connect(args.database)
    self.session = self.Session()
    self.measurement_interface = measurement_interface

  def main(self):
    q = (self.session.query(resultsdb.models.TuningRun)
        .filter_by(state='COMPLETE')
        .order_by('name'))

    if self.args.label:
      q = q.filter(TuningRun.name.in_(
        map(str.strip,self.args.label.split(','))))


    runs = defaultdict(list)
    for tr in q:
      runs[run_name(tr)].append(tr)

    for k, runs in runs.iteritems():
      log.info('%s has %d runs', k, len(runs))
      self.combined_stats_over_time(runs, _.result.time, min)

  def combined_stats_over_time(self,
                               runs,
                               extract_fn,
                               combine_fn,
                               no_data = None):

    by_run = [self.stats_over_time(run, extract_fn, combine_fn, no_data)
              for run in runs]
    max_len = max(map(len, by_run))

    by_run_streams = [Stream() << x << repeat(x[-1], max_len-len(x))
                      for x in by_run]
    by_quanta = zip(*by_run_streams[:])
    print '#sec', 'mean', 'stddev', 'min', 'max'
    for quanta, values in enumerate(by_quanta):
      print quanta*self.args.stats_quanta, mean(values),\
            stddev(values), min(values), max(values)


  def stats_over_time(self, run, extract_fn, combine_fn, no_data = None):
    value_by_quanta = [ no_data ]
    start_date = run.start_date

    q = (self.session.query(DesiredResult)
         .join(Result)
         .filter(DesiredResult.state=='COMPLETE',
                 DesiredResult.tuning_run == run)
         .order_by(DesiredResult.request_date))

    for dr in q:
      quanta = int( (dr.request_date - start_date).total_seconds()
                  / self.args.stats_quanta )
      while len(value_by_quanta) <= quanta:
        value_by_quanta.append(value_by_quanta[-1])

      if value_by_quanta[-1] is no_data:
        value_by_quanta[-1] = extract_fn(dr)
      else:
        value_by_quanta[-1] = combine_fn(value_by_quanta[-1], extract_fn(dr))

    return value_by_quanta










