import logging
import argparse
import hashlib
from datetime import datetime, timedelta
from fn import _
from fn import Stream
from fn.iters import map, filter, reduce
from collections import defaultdict

from opentuner import resultsdb

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--stats', action='store_true',
                       help="run in stats mode")
argparser.add_argument('--stats-quanta', type=int, default=10,
                       help="step size in seconds for binning with --stats")


def hash_args(x):
  return hashlib.sha256(str(sorted(vars(x).items()))).hexdigest()[:20]

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

    runs = defaultdict(list)
    for tr in q:
      runs[tr.name + '_' + hash_args(tr.args)].append(tr)

    for k,v in runs.iteritems():
      log.info('%s has %d runs', k, len(v))







