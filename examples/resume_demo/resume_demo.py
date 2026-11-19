#!/usr/bin/env python
"""
Demonstrate that --resume continues an interrupted tuning run.

The demo tunes a single integer parameter and records every real
measurement in a log file.  A run started with ``--interrupt-after N``
simulates a killed process after N measurements; running the same command
again with ``--resume`` continues the same TuningRun.  ``--verify`` then
checks that

* only one TuningRun exists and it is COMPLETE,
* the seed configurations were not requested again,
* no configuration was ever measured twice,
* the request left in state RUNNING by the killed process was measured,
* the best result known before the interruption was not lost.

See README.md for the three commands.
"""

from __future__ import print_function

import argparse
import json
import os
from collections import Counter

import opentuner
from opentuner import resultsdb
from opentuner.measurement import MeasurementInterface
from opentuner.resultsdb.models import DesiredResult, Result, TuningRun
from opentuner.search.manipulator import (ConfigurationManipulator,
                                          IntegerParameter)

parser = argparse.ArgumentParser(parents=opentuner.argparsers())
parser.add_argument('--measure-log', default='resume-demo-measurements.jsonl',
                    help='append one JSON line per real measurement')
parser.add_argument('--state-file', default='resume-demo-state.json',
                    help='where the interrupted run records its state')
parser.add_argument('--interrupt-after', type=int, default=0,
                    help='simulate a killed process after N measurements')
parser.add_argument('--verify', action='store_true',
                    help='do not tune; check the demo database and logs')


class ResumeDemo(MeasurementInterface):
    def __init__(self, *pargs, **kwargs):
        super(ResumeDemo, self).__init__(*pargs, **kwargs)
        self.measurements = 0

    def manipulator(self):
        manipulator = ConfigurationManipulator()
        manipulator.add_parameter(IntegerParameter('x', 0, 100))
        return manipulator

    def seed_configurations(self):
        # The same configuration twice: a duplicate request inside the run.
        return [{'x': 50}, {'x': 50}]

    def run(self, desired_result, input, limit):
        if (self.args.interrupt_after
                and self.measurements >= self.args.interrupt_after):
            # The measurement driver has already claimed this DesiredResult
            # (state RUNNING) but its measurement never happens.  Record
            # enough information for --verify to recognize it later.
            best = self.driver.results_query(objective_ordered=True).first()
            state = {
                'tuning_run_uuid': desired_result.tuning_run.uuid,
                'pending_config': desired_result.configuration.data,
                'best_time_before_interrupt':
                    None if best is None else best.time,
                'max_generation_before_interrupt': desired_result.generation,
                'requests_before_interrupt':
                    self.driver.requests_query().count(),
            }
            with open(self.args.state_file, 'w') as f:
                json.dump(state, f)
            raise KeyboardInterrupt(
                'simulated kill after %d measurements' % self.measurements)

        config = desired_result.configuration.data
        with open(self.args.measure_log, 'a') as f:
            f.write(json.dumps({'pid': os.getpid(), 'config': config}) + '\n')
        self.measurements += 1
        return Result(time=abs(config['x'] - 42))

    def save_final_config(self, configuration):
        print('final configuration', configuration.data)


def verify(args):
    _engine, Session = resultsdb.connect(args.database)
    session = Session()
    try:
        runs = session.query(TuningRun).all()
        assert len(runs) == 1, 'expected one TuningRun, got %d' % len(runs)
        run = runs[0]
        assert run.state == 'COMPLETE', 'run is %s, not COMPLETE' % run.state

        requests = (session.query(DesiredResult)
                    .filter_by(tuning_run=run).all())
        results = session.query(Result).filter_by(tuning_run=run).all()
        assert len(requests) == args.test_limit, (
            'expected %d requests, got %d' % (args.test_limit, len(requests)))

        seed_requests = [r for r in requests if r.requestor == 'seed']
        assert len(seed_requests) == 2, (
            'seed configurations were requested again after resume: %d rows'
            % len(seed_requests))
        assert len(set(r.result_id for r in seed_requests)) == 1, (
            'the duplicate seed configuration was evaluated more than once')

        per_config = Counter(r.configuration_id for r in results)
        duplicated = [cid for cid, count in per_config.items() if count > 1]
        assert not duplicated, (
            'configurations evaluated more than once: %s' % duplicated)

        with open(args.state_file) as f:
            state = json.load(f)
        assert state['tuning_run_uuid'] == run.uuid, (
            'the resumed process started a new TuningRun')
        resumed_requests = [
            r for r in requests
            if r.generation > state['max_generation_before_interrupt']]
        assert resumed_requests, 'no requests were made after the resume'

        best = min(results, key=lambda r: r.time) if results else None
        assert best is not None
        assert best.time <= state['best_time_before_interrupt'], (
            'the best result found before the interruption was lost')
        assert len(results) >= state['requests_before_interrupt'] - 1, (
            'the resumed run did not add any result')

        with open(args.measure_log) as f:
            measurements = [json.loads(line) for line in f if line.strip()]
        logged = [json.dumps(m['config'], sort_keys=True)
                  for m in measurements]
        repeated = [cfg for cfg, count in Counter(logged).items() if count > 1]
        assert not repeated, 'configurations measured twice: %s' % repeated
        assert len(set(m['pid'] for m in measurements)) >= 2, (
            'the resumed process measured nothing')
        pending = json.dumps(state['pending_config'], sort_keys=True)
        assert pending in logged, (
            'the request left RUNNING by the interrupted process was not '
            'measured')
        assert len(logged) == len(results), (
            'measurement log has %d entries, database has %d results'
            % (len(logged), len(results)))

        print('PASS: %d requests, %d measurements, one TuningRun %s'
              % (len(requests), len(results), run.uuid))
        print('      resumed after generation %d, %d request(s) after resume'
              % (state['max_generation_before_interrupt'],
                 len(resumed_requests)))
    finally:
        session.close()


def main():
    args = parser.parse_args()
    if args.verify:
        verify(args)
        return
    try:
        ResumeDemo.main(args)
    except KeyboardInterrupt as e:
        print('interrupted: %s' % e)
        print('now run the same command with --resume')


if __name__ == '__main__':
    main()
