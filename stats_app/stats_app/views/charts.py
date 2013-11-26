# Method that displays graph to the end user
import matplotlib.pyplot as plt
import urllib

def matplotlibplot_file(input_dir, labels, cols, xlim = None, ylim = None):
    figure = plt.figure()
    index = 0
    data_files = [(input_dir + '%s_percentiles.dat') % l for l in labels]
    for data_file in data_files:
      data = []
      with open(data_file) as f:
        for line in f:
          data.append(line.strip().split(' '))
      plotted_data = [[] for x in xrange(len(cols) - 1)]
      x_indices = []
      for data_point in data[1:]:
        x_indices.append(int(data_point[cols[0]]))
        for i in range(0, len(cols)-1):
          plotted_data[i].append(float(data_point[cols[i+1]]))
      args = []
      for to_plot in plotted_data:
        args.append(x_indices)
        args.append(to_plot)
      plt.plot(*args, label=labels[index])
      index += 1
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

    dir_name = '/afs/csail.mit.edu/u/d/deepakn/opentuner/examples/halide/stats/HalideTuner/apps/bilateral_grid.cpp/unknown/'
    xlim = request.GET.get('xlim')
    if xlim:
      if xlim == 'None':
        xlim = None
      else:
        xlim = [0, int(xlim)]
    ylim = request.GET.get('ylim')
    if ylim:
      if ylim == 'None':
        ylim = None
      else:
        ylim = [0, int(ylim)]
    labels = [u'timeouts', u'always_reorder', u'add_store_at', u'all_options']
    fig = matplotlibplot_file(dir_name, labels, [0,11], xlim=xlim, ylim=ylim)
    canvas=FigureCanvas(fig)
    response=django.http.HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response

def display_full_page(request):
    import django
    from django.shortcuts import render

    xlim = request.GET.get('xlim')
    ylim = request.GET.get('ylim')
    params = { 'xlim': xlim, 'ylim': ylim }
    params = urllib.urlencode(params)
    return render(request, 'charts.html', { 'params': params } )
