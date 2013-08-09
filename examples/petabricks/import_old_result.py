#!/usr/bin/env python

import adddeps  # fix sys.path

import argparse
import json
import logging
import os
import re
import sys
import uuid
import subprocess

try:
  from lxml import etree
except ImportError:
  import xml.etree.ElementTree as etree

import opentuner
from opentuner import resultsdb
from datetime import datetime
from datetime import timedelta
from opentuner.search.objective import ThresholdAccuracyMinimizeTime

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser()
argparser.add_argument('--database', default='opentuner.db/import.db')
argparser.add_argument('--limit', type=float, default=10)
argparser.add_argument('program')
argparser.add_argument('candidatelog')


def run(args, cfg):
  limit = args.limit
  cmd = [args.program,
         '--time',
         '--accuracy',
         '--config=' + cfg,
         '--max-sec=%.10f' % args.limit,
         '-n=%d' % args.n]
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = p.communicate()

  result = opentuner.resultsdb.models.Result()
  try:
    root = etree.XML(out)
    result.time = float(root.find('stats/timing').get('average'))
    result.accuracy = float(root.find('stats/accuracy').get('average'))
    if result.time < limit + 3600:
      result.state = 'OK'
    else:
      # time will be 2**31 if timeout
      result.state = 'TIMEOUT'
  except:
    log.exception('run error')
    log.warning('program crash, out = %s / err = %s', out, err)
    result.state = 'ERROR'
    result.time = float('inf')
    result.accuracy = float('-inf')
  return result


def main(args):
  if '://' not in args.database:
    args.database = 'sqlite:///' + args.database
  engine, Session = opentuner.resultsdb.connect(args.database)
  session = Session()

  program_settings = json.load(open(args.program + '.settings'))
  args.n = program_settings['n']
  args.technique = ['Imported']
  objective = ThresholdAccuracyMinimizeTime(program_settings['accuracy'])

  tuningrun = resultsdb.models.TuningRun(
    uuid=uuid.uuid4().hex,
    name='import',
    args=args,
    start_date=datetime.now(),
    objective=objective,
    program_version=resultsdb.models.ProgramVersion.get(
      session, 'PetaBricksInterface', args.program, 'imported'),
    state='COMPLETE',
  )
  session.add(tuningrun)

  for gen, line in enumerate(open(args.candidatelog)):
    if line[0] != '#':
      line = re.split('\t', line)
      date = tuningrun.start_date + timedelta(seconds=float(line[0]))
      cfg = os.path.normpath(
        os.path.join(os.path.dirname(args.candidatelog), '..', line[5]))
      result = run(args, cfg)
      result.was_new_best = True
      result.tuning_run = tuningrun
      result.collection_date = date
      session.add(result)
      desired_result = resultsdb.models.DesiredResult(
        limit=args.limit,
        tuning_run=tuningrun,
        generation=gen,
        requestor='Imported',
        request_date=date,
        start_date=date,
        result=result,
        state='COMPLETE')
      session.add(desired_result)
      tuningrun.end_date = date
      print gen, date, result.time

  session.commit()


if __name__ == '__main__':
  opentuner.tuningrunmain.init_logging()
  sys.exit(main(argparser.parse_args()))
