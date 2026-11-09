"""Tests for --resume / --resume-uuid (continuing an interrupted TuningRun)."""

import argparse

import pytest

import opentuner
from opentuner import resultsdb
from opentuner.measurement import MeasurementInterface
from opentuner.resultsdb.models import DesiredResult, Result, TuningRun
from opentuner.search.driver import SearchDriver
from opentuner.search.manipulator import (ConfigurationManipulator,
                                          IntegerParameter)
from opentuner.tuningrunmain import TuningRunMain


class Interrupted(Exception):
    """Stands in for the KeyboardInterrupt of a killed process."""


class TinyInterface(MeasurementInterface):
    def manipulator(self):
        manipulator = ConfigurationManipulator()
        manipulator.add_parameter(IntegerParameter('x', 0, 100))
        return manipulator

    def run(self, desired_result, input, limit):
        return Result(time=abs(desired_result.configuration.data['x'] - 42))

    def save_final_config(self, configuration):
        pass


class StopEarlySearchDriver(SearchDriver):
    """Behaves like a run whose process was killed after a few tests."""

    stop_after = 4

    def main(self):
        while not self.convergence_criteria():
            self.run_generation_techniques()
            self.run_generation_results()
            self.generation += 1
            if self.test_count >= self.stop_after:
                raise Interrupted()


def make_args(tmp_path, **overrides):
    parser = argparse.ArgumentParser(parents=opentuner.argparsers())
    args = parser.parse_args([])
    args.database = 'sqlite:///%s' % (tmp_path / 'opentuner.db')
    args.label = 'resume-test'
    args.test_limit = 30
    args.parallelism = 1
    args.seed_configuration = []
    for name, value in overrides.items():
        setattr(args, name, value)
    return args


def run_interrupted(tmp_path):
    args = make_args(tmp_path)
    with pytest.raises(Interrupted):
        TuningRunMain(TinyInterface(args), args,
                      search_driver=StopEarlySearchDriver).main()


def open_db(database):
    _engine, Session = resultsdb.connect(database)
    return Session()


def test_resume_continues_the_interrupted_run(tmp_path):
    run_interrupted(tmp_path)
    args = make_args(tmp_path)

    session = open_db(args.database)
    try:
        run = session.query(TuningRun).one()
        assert run.state == 'ABORTED'
        interrupted_uuid = run.uuid
        recorded = session.query(DesiredResult).count()
        assert recorded >= StopEarlySearchDriver.stop_after
    finally:
        session.close()

    resume_args = make_args(tmp_path, resume=True)
    TuningRunMain(TinyInterface(resume_args), resume_args).main()

    session = open_db(resume_args.database)
    try:
        runs = session.query(TuningRun).all()
        # the same TuningRun was continued, not a second one created
        assert len(runs) == 1
        assert runs[0].uuid == interrupted_uuid
        assert runs[0].state == 'COMPLETE'
        # --test-limit counts every request ever made for the run, so the
        # resumed session stops at 30 in total rather than 4 + 30
        assert session.query(DesiredResult).count() == resume_args.test_limit
    finally:
        session.close()


def test_resume_requeues_requests_left_running(tmp_path):
    run_interrupted(tmp_path)
    args = make_args(tmp_path)

    session = open_db(args.database)
    try:
        # simulate a request the dead process had claimed but never reported
        session.query(DesiredResult).first().state = 'RUNNING'
        session.commit()
    finally:
        session.close()

    resume_args = make_args(tmp_path, resume=True)
    TuningRunMain(TinyInterface(resume_args), resume_args).main()

    session = open_db(resume_args.database)
    try:
        assert session.query(DesiredResult).filter_by(state='RUNNING').count() == 0
        # the re-queued request was measured, not skipped: the resumed session
        # still stops at the same total
        assert session.query(DesiredResult).count() == resume_args.test_limit
    finally:
        session.close()


def test_resume_by_uuid(tmp_path):
    run_interrupted(tmp_path)
    args = make_args(tmp_path)

    session = open_db(args.database)
    try:
        interrupted_uuid = session.query(TuningRun).one().uuid
    finally:
        session.close()

    resume_args = make_args(tmp_path, resume_uuid=interrupted_uuid)
    TuningRunMain(TinyInterface(resume_args), resume_args).main()

    session = open_db(resume_args.database)
    try:
        assert session.query(TuningRun).one().uuid == interrupted_uuid
    finally:
        session.close()


def test_unknown_resume_uuid_raises(tmp_path):
    args = make_args(tmp_path, resume_uuid='deadbeef')
    with pytest.raises(ValueError):
        TuningRunMain(TinyInterface(args), args).main()


def test_without_resume_starts_a_new_run(tmp_path):
    run_interrupted(tmp_path)

    second_args = make_args(tmp_path)
    TuningRunMain(TinyInterface(second_args), second_args).main()

    session = open_db(second_args.database)
    try:
        assert session.query(TuningRun).count() == 2
    finally:
        session.close()


def test_resume_without_unfinished_run_starts_a_new_one(tmp_path):
    run_interrupted(tmp_path)

    # finish the interrupted run, so nothing is resumable any more
    resume_args = make_args(tmp_path, resume=True)
    TuningRunMain(TinyInterface(resume_args), resume_args).main()

    again_args = make_args(tmp_path, resume=True)
    TuningRunMain(TinyInterface(again_args), again_args).main()

    session = open_db(again_args.database)
    try:
        assert session.query(TuningRun).count() == 2
    finally:
        session.close()
