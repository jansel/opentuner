#!/usr/bin/env python

if __name__ == '__main__':
  import adddeps

import argparse
import csv
import hashlib
import itertools
import logging
import math
import os
import sqlalchemy.orm.exc
import subprocess
import sys

from collections import defaultdict
from fn import _
from fn import Stream
from fn.iters import repeat
from pprint import pprint

import opentuner
from opentuner import resultsdb
from opentuner.resultsdb.models import *

log = logging.getLogger('opentuner.utils.stats')

argparser = argparse.ArgumentParser()
argparser.add_argument('--label')
argparser.add_argument('--stats', action='store_true',
                       help="run in stats mode")
argparser.add_argument('--by-request-count', action='store_true',
                       help='report stats by request count')
argparser.add_argument('--stats-quanta', type=float, default=10,
                       help="step size in seconds for binning with --stats")
argparser.add_argument('--stats-dir', default='stats',
                       help="directory to output --stats to")
argparser.add_argument('--stats-input', default="opentuner.db")
argparser.add_argument('--min-runs',  type=int, default=1,
                       help="ignore series with less then N runs")

PCTSTEPS = map(_/20.0, xrange(21))

def mean(vals):
  n = 0.0
  d = 0.0
  for v in vals:
    if v is not None:
      n += v
      d += 1.0
  if d == 0.0:
    return None
  return n/d

def median(vals):
  vals = sorted(vals)
  a = (len(vals)-1)/2
  b = (len(vals))/2
  return (vals[a]+vals[b])/2.0

def percentile(vals, pct):
  vals = sorted(vals)
  pos = (len(vals)-1) * pct
  a = int(math.floor(pos))
  b = min(len(vals) - 1, a + 1)
  return (1.0-(pos-a))*vals[a] + (pos-a)*vals[b]

def variance(vals):
  vals = filter(lambda x: x is not None, vals)
  avg = mean(vals)
  if avg is None:
    return None
  if avg in (float('inf'), float('-inf')):
    return avg
  return mean(map((_ - avg) ** 2, vals))

def stddev(vals):
  var = variance(vals)
  if var is None:
    return None
  return math.sqrt(var)

def hash_args(x):
  d = dict(vars(x))
  for k in ('database', 'results_log', 'results_log_details'):
    d[k] = None
  return hashlib.sha256(str(sorted(d.items()))).hexdigest()[:20]

def run_label(tr, short = False):
  techniques = ','.join(tr.args.technique)
  if not tr.name or tr.name=='unnamed':
    if short:
      return techniques
    else:
      return "%s_%s" % (techniques, hash_args(tr.args)[:6])
  else:
    return tr.name

def run_dir(base, tr):
  return os.path.join(base,
                      tr.program.project,
                      tr.program.name.split('/')[-1],
                      tr.program_version.version[:16])

class StatsMain(object):
  def __init__(self, args):
    self.args = args
    path = args.stats_input
    self.dbs = list()
    for f in os.listdir(path):
      if 'journal' in f:
        continue
      try:
        e, sm = resultsdb.connect('sqlite:///'+os.path.join(path, f))
        self.dbs.append(sm())
      except:
        log.error('failed to load database: %s', 
                  os.path.join(path, f),
                  exc_info=True)

  def main(self):
    dir_label_runs = defaultdict(lambda: defaultdict(list))
    for session in self.dbs:
      q = (session.query(resultsdb.models.TuningRun)
          .filter_by(state='COMPLETE')
          .order_by('name'))

      if self.args.label:
        q = q.filter(TuningRun.name.in_(
          map(str.strip,self.args.label.split(','))))

      for tr in q:
        d = run_dir(self.args.stats_dir, tr)
        d = os.path.normpath(d)
        dir_label_runs[d][run_label(tr)].append((tr, session))

    summary_report = defaultdict(lambda: defaultdict(list))
    for d, label_runs in dir_label_runs.iteritems():
      if not os.path.isdir(d):
        os.makedirs(d)
      session = label_runs.values()[0][0][1]
      objective = label_runs.values()[0][0][0].objective
      all_run_ids = map(_[0].id, itertools.chain(*label_runs.values()))
      q = (session.query(Result)
           .filter(Result.tuning_run_id.in_(all_run_ids))
           .filter(Result.time < float('inf'))
           .filter_by(was_new_best=True, state='OK'))
      total = q.count()
      if total == 0: 
          continue
      q = objective.filter_acceptable(q)
      acceptable = q.count()
      q = q.order_by(*objective.result_order_by_terms())
      best = q.limit(1).one()
      worst = q.offset(acceptable-1).limit(1).one()

      map(len, label_runs.values())

      log.info("%s -- best %.4f / worst %.f4 "
               "-- %d of %d acceptable -- %d techniques with %d to %d runs",
               d,
               best.time,
               worst.time,
               acceptable,
               total,
               len(label_runs.values()),
               min(map(len, label_runs.values())),
               max(map(len, label_runs.values())))

      for label, runs in sorted(label_runs.items()):
        if len(runs) < self.args.min_runs:
          print len(runs) ,self.args.min_runs
          continue
        log.debug('%s/%s has %d runs %s',d, label, len(runs), runs[0][0].args.technique)
        self.combined_stats_over_time(d, label, runs, objective, worst, best)

        final_scores = list()
        for run, session in runs:
          try:
            final = (session.query(Result)
                    .filter_by(tuning_run=run,
                               configuration=run.final_config)
                    .limit(1)
                    .one())
          except sqlalchemy.orm.exc.NoResultFound:
            continue
          final_scores.append(objective.stats_quality_score(final, worst, best))
        final_scores.sort()
        if final_scores:
          norm = objective.stats_quality_score(best, worst, best)
          if norm > 0.00001:
            summary_report[d][run_label(run, short=True)] = (
                percentile(final_scores, 0.5) / norm,
                percentile(final_scores, 0.1) / norm,
                percentile(final_scores, 0.9) / norm,
              )
          else:
            summary_report[d][run_label(run, short=True)] = (
                percentile(final_scores, 0.5) + norm + 1.0,
                percentile(final_scores, 0.1) + norm + 1.0,
                percentile(final_scores, 0.9) + norm + 1.0,
              )


    with open(self.args.stats_dir+ "/summary.dat", 'w') as o:
      # make summary report
      keys = sorted(reduce(set.union,
                           [set(x.keys()) for x in summary_report.values()],
                           set()))
      print >>o, '#####',
      for k in keys:
        print >>o, k,
      print >>o
      for d, label_vals in sorted(summary_report.items()):
        print >>o, d.split('/')[-2],
        for k in keys:
          if k in label_vals:
            print >>o, '-', label_vals[k][0], label_vals[k][1], label_vals[k][2],
          else:
            print >>o, '-', '-', '-', '-',
        print >>o

    if keys:
      plotcmd = ["""1 w lines lt 1 lc rgb "black" notitle""",
                 """'summary.dat' using 3:4:5:xtic(1) ti "%s" """ % keys[0]]
      for n, k in enumerate(keys[1:]):
        plotcmd.append("""'' using %d:%d:%d ti "%s" """ % (
                        4*n + 7,
                        4*n + 8,
                        4*n + 9,
                        k))
      self.gnuplot_summary_file(self.args.stats_dir, 'summary', plotcmd)



    for d, label_runs in dir_label_runs.iteritems():
      labels = [k for k,v in label_runs.iteritems()
                if len(v)>=self.args.min_runs]
      self.gnuplot_file(d,
                        "medianperfe",
                        ['"%s_percentiles.dat" using 1:12:4:18 with errorbars title "%s"' % (l,l) for l in labels])
      self.gnuplot_file(d,
                        "meanperfe",
                        ['"%s_percentiles.dat" using 1:21:4:18 with errorbars title "%s"' % (l,l) for l in labels])
      self.gnuplot_file(d,
                        "medianperfl",
                        ['"%s_percentiles.dat" using 1:12 with lines title "%s"' % (l,l) for l in labels])
      self.gnuplot_file(d,
                        "meanperfl",
                        ['"%s_percentiles.dat" using 1:21 with lines title "%s"' % (l,l) for l in labels])

    # print
    # print "10% Scores", d
    # pprint(self.technique_scores(d, labels, '0.1'))
    # print
    # print "90% Scores", d
    # pprint(self.technique_scores(d, labels, '0.9'))
    # print
    # print "Mean Scores", d
    # pprint(self.technique_scores(d, labels, 'mean'))
      print
      print "Median Scores", d
      pprint(self.technique_scores(d, labels, '0.5'))


  def technique_scores(self, directory, labels, ykey, xkey='#sec', factor=10.0):
    max_duration = None
    min_value = float('inf')
    for label in labels:
      try:
        dr = csv.DictReader(open(os.path.join(directory,label+"_percentiles.dat")), delimiter=' ', lineterminator='\n')
        lastrow = list(dr)[-1]
        max_duration = max(max_duration, float(lastrow[xkey]))
        min_value = min(min_value, float(lastrow[ykey]))
      except:
        log.exception("failed computing score")

    scores = list()

    for label in labels:
      try:
        dr = csv.DictReader(open(os.path.join(directory,label+"_percentiles.dat")), delimiter=' ', lineterminator='\n')
        score = 0.0
        lastsec = 0.0
        value = float('inf')
        for row in dr:
          duration = float(row[xkey]) - lastsec
          lastsec = float(row[xkey])
          value = float(row[ykey])
          score += duration * (value - min_value)
        score += (factor*max_duration - lastsec) * (value - min_value)
        scores.append((score, label))
      except:
        log.exception("failed computing score")

    return sorted(scores)


  def combined_stats_over_time(self,
                               output_dir,
                               label,
                               runs,
                               objective,
                               worst,
                               best,
                               ):
    """
    combine stats_over_time() vectors for multiple runs
    """

    #extract_fn = lambda dr: objective.stats_quality_score(dr.result, worst, best)
    extract_fn = _.result.time
    combine_fn = min
    no_data = 999

    log.debug("writing stats for %s to %s", label, output_dir)
    by_run = [self.stats_over_time(session, run, extract_fn, combine_fn, no_data)
              for run, session in runs]
    max_len = max(map(len, by_run))

    by_run_streams = [Stream() << x << repeat(x[-1], max_len-len(x))
                      for x in by_run]
    by_quanta = zip(*by_run_streams[:])

    def data_file(suffix, headers, value_function):
      with open(os.path.join(output_dir, label+suffix), 'w') as fd:
        out = csv.writer(fd, delimiter=' ', lineterminator='\n')
        out.writerow(['#sec'] + headers)
        for quanta, values in enumerate(by_quanta):
          sec = quanta*self.args.stats_quanta
          out.writerow([sec] + value_function(values))

   #data_file('_details.dat',
   #          map(lambda x: 'run%d'%x, xrange(max_len)),
   #          list)
   #self.gnuplot_file(output_dir,
   #                  label+'_details',
   #                  [('"'+label+'_details.dat"'
   #                    ' using 1:%d'%i +
   #                    ' with lines'
   #                    ' title "Run %d"'%i)
   #                   for i in xrange(max_len)])

    data_file('_mean.dat',
              ['#sec', 'mean', 'stddev'],
              lambda values: [mean(values), stddev(values)])
    self.gnuplot_file(output_dir,
                      label+'_mean',
                      ['"'+label+'_mean.dat" using 1:2 with lines title "Mean"'])

    def extract_percentiles(values):
      values = sorted(values)
      return ([values[int(round(p*(len(values)-1)))] for p in PCTSTEPS]
             + [mean(values)])
    data_file("_percentiles.dat", PCTSTEPS + ['mean'], extract_percentiles)
    self.gnuplot_file(output_dir,
                      label+'_percentiles',
                      reversed([
                        '"'+label+'_percentiles.dat" using 1:2  with lines title "0%"',
                      # '""                          using 1:3  with lines title "5%"',
                        '""                          using 1:4  with lines title "10%"',
                      # '""                          using 1:5  with lines title "25%"',
                        '""                          using 1:6  with lines title "20%"',
                      # '""                          using 1:7  with lines title "35%"',
                        '""                          using 1:8  with lines title "30%"',
                      # '""                          using 1:9  with lines title "45%"',
                        '""                          using 1:10 with lines title "40%"',
                      # '""                          using 1:11 with lines title "55%"',
                        '""                          using 1:12 with lines title "50%"',
                      # '""                          using 1:13 with lines title "65%"',
                        '""                          using 1:14 with lines title "70%"',
                      # '""                          using 1:15 with lines title "75%"',
                        '""                          using 1:16 with lines title "80%"',
                      # '""                          using 1:17 with lines title "85%"',
                        '""                          using 1:18 with lines title "90%"',
                      # '""                          using 1:19 with lines title "95%"',
                        '"'+label+'_percentiles.dat" using 1:20 with lines title "100%"',
                       ]))

  def gnuplot_file(self, output_dir, prefix, plotcmd):
    with open(os.path.join(output_dir, prefix+'.gnuplot'), 'w') as fd:
      print >>fd, 'set terminal postscript eps enhanced color'
      print >>fd, 'set output "%s"' % (prefix+'.eps')
      print >>fd, 'set ylabel "Execution Time (seconds)"'
      print >>fd, 'set xlabel "Autotuning Time (seconds)"'
      print >>fd, 'plot', ',\\\n'.join(plotcmd)

    try:
      subprocess.call(['gnuplot', prefix+'.gnuplot'], cwd=output_dir, stdin=None)
    except OSError:
      log.error("command gnuplot not found")

  def gnuplot_summary_file(self, output_dir, prefix, plotcmd):
    with open(os.path.join(output_dir, prefix+'.gnuplot'), 'w') as fd:
      print >>fd, 'set terminal postscript eps enhanced color'
      print >>fd, 'set output "%s"' % (prefix+'.eps')
      print >>fd, '''
set boxwidth 0.9
set style fill solid 1.00 border 0
set style histogram errorbars gap 2 lw 1
set style data histograms
set xtics rotate by -45
set bars 0.5
set yrange [0:20]

set yrange [0:10]
set key out vert top left
set size 1.5,1
set ytics 1

'''
      print >>fd, 'plot', ',\\\n'.join(plotcmd)
    subprocess.call(['gnuplot', prefix+'.gnuplot'], cwd=output_dir, stdin=None)


  def stats_over_time(self,
                      session,
                      run,
                      extract_fn,
                      combine_fn,
                      no_data = None):
    """
    return reduce(combine_fn, map(extract_fn, data)) for each quanta of the
    tuning run
    """
    value_by_quanta = [ no_data ]
    start_date = run.start_date

    subq = (session.query(Result.id)
           .filter_by(tuning_run = run, was_new_best = True, state='OK'))

    q = (session.query(DesiredResult)
         .join(Result)
         .filter(DesiredResult.state=='COMPLETE',
                 DesiredResult.tuning_run == run,
                 DesiredResult.result_id.in_(subq.subquery()))
         .order_by(DesiredResult.request_date))

    first_id = None
    for dr in q:
      if first_id is None:
        first_id = dr.id
      td = (dr.request_date - start_date)
      duration = td.seconds + (td.days * 24 * 3600.0)
      if self.args.by_request_count:
        quanta = dr.id - first_id
      else:
        quanta = int(duration / self.args.stats_quanta)
      while len(value_by_quanta) <= quanta:
        value_by_quanta.append(value_by_quanta[-1])

      if value_by_quanta[-1] is no_data:
        value_by_quanta[-1] = extract_fn(dr)
      else:
        value_by_quanta[-1] = combine_fn(value_by_quanta[-1], extract_fn(dr))

    return value_by_quanta





if __name__ == '__main__':
  opentuner.tuningrunmain.init_logging()
  sys.exit(StatsMain(argparser.parse_args()).main())


