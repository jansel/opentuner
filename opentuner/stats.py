import argparse
import csv
import hashlib
import logging
import subprocess
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
argparser.add_argument('--stats-quanta', type=float, default=10,
                       help="step size in seconds for binning with --stats")
argparser.add_argument('--stats-dir', default='stats',
                       help="directory to output --stats to")

PCTSTEPS = map(_/20.0, xrange(21))

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
  techniques = ','.join(tr.args.technique)
  if not tr.name or tr.name=='unnamed':
    return "%s_%s" % (techniques, hash_args(tr.args)[:6])
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
                      tr.program_version.version[:16])

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

    dir_to_plots = defaultdict(list)
    for k, runs in runs.iteritems():
      log.info('%s has %d runs %s', k, len(runs), runs[0].args.technique)
      d = run_dir(self.args.stats_dir, runs[0])
      if not os.path.isdir(d):
        os.makedirs(d)
      label = run_label(runs[0])
      dir_to_plots[d].append(label)
      self.combined_stats_over_time(d, label, runs, _.result.time, min)

    for d, labels in dir_to_plots.iteritems():
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

      print
      print "10% Scores"
      pprint(self.technique_scores(d, labels, '0.1'))
      print
      print "90% Scores"
      pprint(self.technique_scores(d, labels, '0.9'))
      print
      print "Mean Scores"
      pprint(self.technique_scores(d, labels, 'mean'))
      print
      print "Median Scores"
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
                               extract_fn,
                               combine_fn,
                               no_data = None):
    '''
    combine stats_over_time() vectors for multiple runs
    '''

    log.info("writing stats for %s to %s", label, output_dir)
    by_run = [self.stats_over_time(run, extract_fn, combine_fn, no_data)
              for run in runs]
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
                        '""                          using 1:3  with lines title "5%"',
                        '""                          using 1:4  with lines title "10%"',
                        '""                          using 1:5  with lines title "25%"',
                        '""                          using 1:6  with lines title "20%"',
                        '""                          using 1:7  with lines title "35%"',
                        '""                          using 1:8  with lines title "30%"',
                        '""                          using 1:9  with lines title "45%"',
                        '""                          using 1:10 with lines title "40%"',
                        '""                          using 1:11 with lines title "55%"',
                        '""                          using 1:12 with lines title "50%"',
                        '""                          using 1:13 with lines title "65%"',
                        '""                          using 1:14 with lines title "70%"',
                        '""                          using 1:15 with lines title "75%"',
                        '""                          using 1:16 with lines title "80%"',
                        '""                          using 1:17 with lines title "85%"',
                        '""                          using 1:18 with lines title "90%"',
                        '""                          using 1:19 with lines title "95%"',
                        '"'+label+'_percentiles.dat" using 1:20 with lines title "100%"',
                       ]))

  def gnuplot_file(self, output_dir, prefix, plotcmd):
    with open(os.path.join(output_dir, prefix+'.gnuplot'), 'w') as fd:
      print >>fd, 'set terminal postscript eps enhanced color'
      print >>fd, 'set output "%s"' % (prefix+'.pdf')
      print >>fd, 'set ylabel "Execution Time (seconds)"'
      print >>fd, 'set xlabel "Autotuning Time (seconds)"'
      print >>fd, 'plot', ',\\\n'.join(plotcmd)
    subprocess.call(['gnuplot', prefix+'.gnuplot'], cwd=output_dir)



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










