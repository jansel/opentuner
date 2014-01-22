import datetime
import django
from django.shortcuts import render
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
import random

from opentuner.utils import stats_matplotlib as stats


def display_graph(request):
  """
  Handles request to display graph with provided parameters
  """
  request_dict = dict(request.GET.iterlists())

  xlim = request_dict.get('xlim', None)
  if xlim:
    xlim = int(xlim[0])
  else:
    xlim = 5000
  xlim = [0, xlim]

  ylim = request_dict.get('ylim', None)
  if ylim:
    ylim = int(ylim[0])
  else:
    ylim = 10
  ylim = [0, ylim]

  labels = request_dict.get('labels', None)

  disp_types = request_dict.get('disp_type', None)
  if not disp_types:
    disp_types = ['median']

  fig = stats.matplotlibplot_file(labels, xlim=xlim, ylim=ylim, disp_types=disp_types)
  canvas = FigureCanvas(fig)
  response = django.http.HttpResponse(content_type='image/png')
  canvas.print_png(response)
  return response


def display_full_page(request):
  """
  Handles request to display the full page
  """
  all_labels = stats.get_all_labels()
  label_list = get_label_list(all_labels)
  html = render(request, 'charts.html')
  content = html.content
  content = content.format(label_list)
  html.content = content
  return html


def get_label_list(all_labels):
  """
  Returns list of html form inputs corresponding to the different
  labels in the provided db file
  """
  label_list = ''
  for label in all_labels:
    label_list += '<b>%s</b>:<input type="checkbox" name="labels" value="%s">' % (label, label)
  return label_list

