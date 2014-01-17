# Method that displays graph to the end user
import matplotlib.pyplot as plt
import os
import urllib

import sys
# sys.path.append('../../..')
# sys.path.append('..')
import opentuner
from opentuner import resultsdb

import itertools
from collections import defaultdict
from fn import _
from fn import Stream
from fn.iters import repeat
import math
import numpy

PCTSTEPS = map(_/20.0, xrange(21))

def mean(vals):
  filtered_values = [float(x) for x in vals if x is not None]
  if (len(filtered_values) == 0):
    return None
  return numpy.mean(numpy.array(filtered_values))

def stddev(vals):
  filtered_values = [float(x) for x in vals if x is not None]
  if (len(filtered_values) == 0):
    return None
  return math.sqrt(numpy.var(numpy.array(filtered_values)))

def get_dbs(path):
  dbs = list()
  for f in os.listdir(path):
    if 'journal' in f:
      continue
    try:
      db_path = os.path.join(path, f)
      e, sm = resultsdb.connect('sqlite:///' + db_path)
      dbs.append(sm())
    except Exception as e:
      print e
      print "Error encountered while connecting to db"
  return dbs


def matplotlibplot_file(labels, xlim = None, ylim = None, disp_types=['median']):
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


def display_graph(request):
    import random
    import django
    import datetime
    
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.dates import DateFormatter

    request_dict = dict(request.GET.iterlists())
    xlim = request_dict.get('xlim', None)
    if xlim:
      xlim = xlim[0]
      if xlim == 'None':
        xlim = [0, 5000]
      else:
        xlim = [0, int(xlim)]
    else:
      xlim = [0, 5000]
    ylim = request_dict.get('ylim', None)
    if ylim:
      ylim = ylim[0]
      if ylim == 'None':
        ylim = [0, 10]
      else:
        ylim = [0, int(ylim)]
    else:
      ylim = [0, 10]
    labels = request_dict.get('labels', None)
    if labels:
      if labels == ['None']:
        labels = None
    disp_types = request_dict.get('disp_type', None)
    if disp_types:
      if disp_types == ['None']:
        disp_types = ['median'] # Default value is median
    else:
      disp_types = ['median']
    fig = matplotlibplot_file(labels, xlim=xlim, ylim=ylim, disp_types=disp_types)
    canvas=FigureCanvas(fig)
    response=django.http.HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response


def display_full_page(request):
    import django
    from django.shortcuts import render

    all_labels = get_all_labels()
    label_list = get_list(all_labels)
    html = render(request, 'charts.html')
    content = html.content
    content = content.format(label_list)
    html.content = content
    return html


def get_list(all_labels):
  label_list = ''
  for label in all_labels:
    label_list += '<b>%s</b>:<input type="checkbox" name="labels" value="%s">' % (label, label)
  return label_list


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
    '''
    combine stats_over_time() vectors for multiple runs
    '''

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
    return (mean_values, percentile_values)


def stats_over_time(session,
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
  # dbs = get_dbs('/afs/csail.mit.edu/u/d/deepakn/opentuner/examples/halide/opentuner.db')
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
    directory = os.getcwd()
    # dbs = get_dbs('/afs/csail.mit.edu/u/d/deepakn/opentuner/examples/halide/opentuner.db')
    # dbs = get_dbs('opentuner.db')
    dbs = get_dbs(directory)
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
