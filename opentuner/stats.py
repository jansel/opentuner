import argparse
import hashlib
import logging
import math
import os

from collections import defaultdict
from datetime import datetime, timedelta
from fn import _, F
from fn import Stream
from fn.iters import repeat
from pprint import pprint

from opentuner import resultsdb
from opentuner.resultsdb.models import *

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--stats', action='store_true',
                       help="run in stats mode")
argparser.add_argument('--stats-quanta', type=float, default=60,
                       help="step size in seconds for binning with --stats")
argparser.add_argument('--stats-dir', default='stats',
                       help="directory to output --stats to")

def mean(vals):
  return sum(vals)/float(len(vals))

def median(vals):
  vals = sorted(vals)
  a = (len(vals)-1)/2
  b = (len(vals))/2
  return (vals[a]+vals[b])/2.0

def variance(vals):
  avg = mean(vals)
  return mean(map((_ - avg) ** 2, vals))

def stddev(vals):
  return math.sqrt(variance(vals))

def hash_args(x):
  return hashlib.sha256(str(sorted(vars(x).items()))).hexdigest()[:20]

def run_label(tr):
  if not tr.name or tr.name=='unnamed':
    return hash_args(tr.args)
  else:
    return tr.label

def run_name(tr):
  return "%s/%s/%s[%s]" % (
      tr.program.project,
      tr.program.name,
      tr.program_version.version,
      run_label(tr),
    )

def run_dir(base, tr):
  return os.path.join(base,
                      tr.program.project,
                      tr.program.name,
                      tr.program_version.version)

class StatsMain(object):
  def __init__(self, measurement_interface, session, args):
    self.args = args
    self.session = session
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
      log.info('%s has %d runs %s', k, len(runs), runs[0].args.technique)
      d = run_dir(self.args.stats_dir, runs[0])
      if not os.path.isdir(d):
        os.makedirs(d)
      self.combined_stats_over_time(d,
                                    run_label(runs[0]),
                                    runs,
                                    _.result.time,
                                    min)

  def combined_stats_over_time(self,
                               output_dir,
                               label,
                               runs,
                               extract_fn,
                               combine_fn,
                               no_data = None):
    '''
    combine stats_over_time() vectors for multiple runs
    '''

    log.info("writing stats for %s to %s", label, output_dir)
    details     = open(os.path.join(output_dir, label+"_details.dat"), 'w')
    percentiles = open(os.path.join(output_dir, label+"_percentiles.dat"), 'w')
    means       = open(os.path.join(output_dir, label+"_mean.dat"), 'w')

    by_run = [self.stats_over_time(run, extract_fn, combine_fn, no_data)
              for run in runs]
    max_len = max(map(len, by_run))

    by_run_streams = [Stream() << x << repeat(x[-1], max_len-len(x))
                      for x in by_run]
    by_quanta = zip(*by_run_streams[:])
    pctsteps = map(_/20.0, xrange(21))
    print >>means,       '#sec', 'mean', 'stddev'
    print >>percentiles, '#sec', ' '.join(map(str, pctsteps))
    print >>details,     '#sec', 'runs...'
    for quanta, values in enumerate(by_quanta):
      sec = quanta*self.args.stats_quanta
      print >>means,       sec, mean(values), stddev(values)
      print >>details,     sec, ' '.join(map(str, values))

      values = sorted(values)
      idxs = map(F() << int << round << (_ * (len(values)-1)),  pctsteps)
      print >>percentiles, sec, ' '.join([str(values[i]) for i in idxs])

    details    .close()
    percentiles.close()
    means      .close()

  def stats_over_time(self,
                      run,
                      extract_fn,
                      combine_fn,
                      no_data = None):
    '''
    return reduce(combine_fn, map(extract_fn, data)) for each quanta of the
    tuning run
    '''
    value_by_quanta = [ no_data ]
    start_date = run.start_date

    subq = (self.session.query(Result.id)
           .filter_by(tuning_run = run, was_new_best = True))

    q = (self.session.query(DesiredResult)
         .join(Result)
         .filter(DesiredResult.state=='COMPLETE',
                 DesiredResult.tuning_run == run,
                 DesiredResult.result_id.in_(subq.subquery()))
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










