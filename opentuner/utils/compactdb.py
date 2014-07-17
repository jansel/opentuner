#!/usr/bin/env python

if __name__ == '__main__':
  import adddeps

import argparse
import logging
import sys

import opentuner
from opentuner.resultsdb.models import *

log = logging.getLogger('opentuner.utils.compactdb')

argparser = argparse.ArgumentParser()
argparser.add_argument('database')
argparser.add_argument('--level', type=int, default=2)


def main(args):
  if '://' not in args.database:
    args.database = "sqlite:///" + args.database
  engine, Session = opentuner.resultsdb.connect(args.database)
  session = Session()

  config_count = session.query(Configuration).count()
  # result_count = session.query(Result).count()
  # desired_result_count = session.query(DesiredResult).count()

  if args.level >= 1:
    q = (session.query(Configuration)
         .filter(~Configuration.id.in_(session.query(Result.configuration_id)
                                       .filter_by(was_new_best=True)
                                       .subquery()))
         .filter(Configuration.data != None))

    log.info("%s: compacted %d of %d Configurations",
             args.database,
             q.update({'data': None}, False),
             config_count)
    session.commit()

  if args.level >= 2:
    session.execute('VACUUM;')
    session.commit()

  log.info('done')


if __name__ == '__main__':
  opentuner.tuningrunmain.init_logging()
  sys.exit(main(argparser.parse_args()))


