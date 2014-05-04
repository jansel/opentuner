#!usr/bin/python

if __name__ == '__main__':
  import adddeps

import itertools
import math
import matplotlib.pyplot as plt
import numpy
import os
import sqlalchemy
import sqlalchemy.orm.exc

from collections import defaultdict
from fn import _
from fn import Stream
from fn.iters import repeat
from opentuner import resultsdb

PCTSTEPS = map(_/20.0, xrange(21))


def mean(vals):
  """
  Arguments,
    vals: List of floating point numbers
  Returns,
    The mean of the numbers in the input list
    None if all values in the list are None
  """
  filtered_values = [float(x) for x in vals if x is not None]
  if len(filtered_values) == 0:
    return None
  return numpy.mean(numpy.array(filtered_values))


def stddev(vals):
  """
  Arguments,
    vals: List of floating point numbers
  Returns,
    The standard deviation of numbers in the input list
    None if all values in the list are None
  """
  filtered_values = [float(x) for x in vals if x is not None]
  if len(filtered_values) == 0:
    return None
  return math.sqrt(numpy.var(numpy.array(filtered_values)))


def get_dbs(path, db_type='sqlite:///'):
  """
  Arguments,
    path: Path of directory containing .db files
  Returns,
    A list of (engine, session) pairs to the dbs pointed to by
    the db files
  """
  dbs = list()
  for f in os.listdir(path):
    if 'journal' in f:
      continue
    try:
      db_path = os.path.join(path, f)
      e, sm = resultsdb.connect(db_type + db_path)
      dbs.append(sm())
    except Exception as e:
      print e
      print "Error encountered while connecting to db"
  return dbs


def matplotlibplot_file(labels, xlim = None, ylim = None, disp_types=['median']):
  """
  Arguments,
    labels: List of labels that need to be included in the plot
    xlim: Integer denoting the maximum X-coordinate in the plot
    ylim: Integer denoting the maximum Y-coordinate in the plot
    disp_types: List of measures that are to be displayed in the plot
  Returns,
    A figure object representing the required plot
  """

  figure = plt.figure()
  values = get_values(labels)
  for label in values:
    (mean_values, percentile_values) = values[label]
    for disp_type in disp_types:
      cols = None
      data = percentile_values

      if disp_type == 'median':
        cols = [11]
      elif disp_type == 'mean':
        cols = [1]
        data = mean_values
      elif disp_type == 'all_percentiles':
        cols = range(1,22)

      plotted_data = [[] for x in xrange(len(cols))]

      x_indices = []
      for data_point in data[1:]:
        x_indices.append(int(data_point[0]))
        for i in range(0, len(cols)):
          plotted_data[i].append(float(data_point[cols[i]]))
      args = []
      for to_plot in plotted_data:
        args.append(x_indices)
        args.append(to_plot)

      plt.plot(*args, label='%s(%s)' % (label, disp_type))

  if xlim is not None:
    plt.xlim(xlim)
  if ylim is not None:
    plt.ylim(ylim)

  plt.xlabel('Autotuning Time (seconds)')
  plt.ylabel('Execution Time (seconds)')
  plt.legend(loc='upper right')
  return figure


def run_label(tr):
  techniques = ','.join(tr.args.technique)
  if not tr.name or tr.name == 'unnamed':
    return techniques
  return tr.name


def combined_stats_over_time(label,
                             runs,
                             objective,
                             worst,
                             best,
                             ):
  """
  combine stats_over_time() vectors for multiple runs
  """

  extract_fn = _.result.time
  combine_fn = min
  no_data = 999

  by_run = [stats_over_time(session, run, extract_fn, combine_fn, no_data)
            for run, session in runs]
  max_len = max(map(len, by_run))

  by_run_streams = [Stream() << x << repeat(x[-1], max_len-len(x))
                    for x in by_run]
  by_quanta = zip(*by_run_streams[:])

  # TODO: Fix this, this variable should be configurable
  stats_quanta = 10
  def get_data(value_function):
    final_values = []
    for quanta, values in enumerate(by_quanta):
      sec = quanta*stats_quanta
      final_values.append([sec] + value_function(values))
    return final_values

  mean_values = get_data(lambda values: [mean(values), stddev(values)])

  def extract_percentiles(values):
    values = sorted(values)
    return ([values[int(round(p*(len(values)-1)))] for p in PCTSTEPS]
           + [mean(values)])
  percentile_values = get_data(extract_percentiles)
  return mean_values, percentile_values


def stats_over_time(session,
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

  subq = (session.query(resultsdb.models.Result.id)
         .filter_by(tuning_run = run, was_new_best = True, state='OK'))

  q = (session.query(resultsdb.models.DesiredResult)
       .join(resultsdb.models.Result)
       .filter(resultsdb.models.DesiredResult.state=='COMPLETE',
               resultsdb.models.DesiredResult.tuning_run == run,
               resultsdb.models.DesiredResult.result_id.in_(subq.subquery()))
       .order_by(resultsdb.models.DesiredResult.request_date))

  first_id = None
  for dr in q:
    if first_id is None:
      first_id = dr.id
    td = (dr.request_date - start_date)
    duration = td.seconds + (td.days * 24 * 3600.0)
    # TODO: Make this variable configurable
    by_request_count = True
    stats_quanta = 10
    if by_request_count:
      quanta = dr.id - first_id
    else:
      quanta = int(duration / stats_quanta)
    while len(value_by_quanta) <= quanta:
      value_by_quanta.append(value_by_quanta[-1])

    if value_by_quanta[-1] is no_data:
      value_by_quanta[-1] = extract_fn(dr)
    else:
      value_by_quanta[-1] = combine_fn(value_by_quanta[-1], extract_fn(dr))

  return value_by_quanta


def get_all_labels():
  """
  Returns,
    List of labels that are in the complete state
  """
  dbs = get_dbs(os.getcwd())
  all_labels = list()
  for db in dbs:
    all_labels.extend(db.query(resultsdb.models.TuningRun.name)
                        .filter_by(state='COMPLETE')
                        .distinct()
                        .all())
  all_labels = [str(element[0]) for element in all_labels]
  return all_labels


def get_values(labels):
  """
  Arguments,
    labels: List of labels whose values are of interest
  Returns,
    A list of (mean, percentile) tuples, corresponding to the
    provided list of labels
  """
  dbs = get_dbs(os.getcwd())
  dir_label_runs = defaultdict(lambda: defaultdict(list))
  for db in dbs:
    q = (db.query(resultsdb.models.TuningRun)
            .filter_by(state='COMPLETE')
            .order_by('name'))
    if labels:
      q = q.filter(resultsdb.models.TuningRun.name.in_(labels))
    for tr in q:
      dir_label_runs[run_label(tr)][run_label(tr)].append((tr, db))
  all_run_ids = list()
  returned_values = {}
  for d, label_runs in dir_label_runs.iteritems():
    all_run_ids = map(_[0].id, itertools.chain(*label_runs.values()))
    session = label_runs.values()[0][0][1]
    objective = label_runs.values()[0][0][0].objective

    q = (session.query(resultsdb.models.Result)
         .filter(resultsdb.models.Result.tuning_run_id.in_(all_run_ids))
         .filter(resultsdb.models.Result.time < float('inf'))
         .filter_by(was_new_best=True, state='OK'))
    total = q.count()
    q = objective.filter_acceptable(q)
    acceptable = q.count()
    q = q.order_by(*objective.result_order_by_terms())
    best = q.limit(1).one()
    worst = q.offset(acceptable - 1).limit(1).one()

    for label, runs in sorted(label_runs.items()):
      (mean_values, percentile_values) = combined_stats_over_time(label, runs, objective, worst, best)
      returned_values[label] = (mean_values, percentile_values)
      final_scores = list()
      for run, session in runs:
        try:
          final = (session.query(resultsdb.models.Result)
                  .filter_by(tuning_run = run,
                             configuration = run.final_config)
                  .limit(1).one())
        except sqlalchemy.orm.exc.NoResultFound:
          continue
        final_scores.append(objective.stats_quality_score(final, worst, best))
      final_scores.sort()
  return returned_values

if __name__ == '__main__':
    labels = [u'timeouts', u'always_reorder', u'add_store_at', u'all_options']
    get_values(labels)
    print get_all_labels()
