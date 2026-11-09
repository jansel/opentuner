import argparse
import copy
import logging
import math
import os
import socket
import sys
import time
import uuid
from datetime import datetime

from opentuner import resultsdb
from opentuner.measurement.driver import MeasurementDriver
from opentuner.search.driver import SearchDriver

log = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(add_help=False)
argparser.add_argument('--label', help="name for the TuningRun")
argparser.add_argument('--print-search-space-size', action='store_true',
                       help="Print out the estimated size of the search space and exit")
argparser.add_argument('--database', help="database to store tuning results in")
argparser.add_argument('--print-params', '-pp', action='store_true',
                       help='show parameters of the configuration being tuned')
argparser.add_argument('--resume', action='store_true',
                       help='continue the most recent unfinished TuningRun with the '
                            'same label instead of starting a new one; the search '
                            'continues from its recorded results, and --test-limit '
                            'counts every request ever made for that run')
argparser.add_argument('--resume-uuid', metavar='UUID',
                       help='continue the TuningRun with this uuid (see '
                            'opentuner/utils/stats.py or the results database)')


class CleanStop(Exception):
    pass


class LogFormatter(logging.Formatter):
    def format(self, record):
        record.relativeCreated /= 1000.0
        try:
            return super(LogFormatter, self).format(record)
        except:
            return _OldFormatter.format(self, record)


_OldFormatter = logging.Formatter
logging.Formatter = LogFormatter

try:
    from logging.config import dictConfig
except ImportError:
    from .utils.dictconfig import dictConfig

the_logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'console': {'format': '[%(relativeCreated)6.0fs] %(levelname)7s %(name)s: %(message)s'},
                   'file': {'format': '[%(asctime)-15s] %(levelname)7s %(name)s: %(message)s @%(filename)s:%(lineno)d'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'console', 'level': 'INFO'},
                 'file': {'class': 'logging.FileHandler', 'filename': 'opentuner.log', 'formatter': 'file', 'level': 'WARNING'}},
    'loggers': {'': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': True}}
}


def init_logging():
    dictConfig(the_logging_config)
    global init_logging
    init_logging = lambda: None


class TuningRunMain:
    def __init__(self, measurement_interface, args, search_driver=SearchDriver, measurement_driver=MeasurementDriver):
        init_logging()
        manipulator = measurement_interface.manipulator()

        if args.print_search_space_size:
            print("10^{:.2f}".format(math.log(manipulator.search_space_size(), 10)))
            sys.exit(0)
        if args.print_params:
            cfg = manipulator.seed_config()
            d = manipulator.parameters_dict(cfg)
            params_dict = {}
            for k in d:
                cls = d[k].__class__.__name__
                p = (k, d[k].search_space_size())
                params_dict.setdefault(cls, []).append(p)
            for k, v in params_dict.items():
                print(k, v)
                print()
            sys.exit(0)

        input_manager = measurement_interface.input_manager()
        objective = measurement_interface.objective()

        if not args.database:
            args.database = 'sqlite:///' + os.path.join('opentuner.db', socket.gethostname() + '.db')
        if '://' not in args.database:
            args.database = 'sqlite:///' + args.database
        if not args.label:
            args.label = 'unnamed'

        self.fake_commit = True
        self.args = args
        self.engine, self.Session = resultsdb.connect(args.database)
        self.session = self.Session()
        self.tuning_run = None
        self.search_driver_cls = search_driver
        self.measurement_driver_cls = measurement_driver
        self.measurement_interface = measurement_interface
        self.input_manager = input_manager
        self.manipulator = manipulator
        self.objective = objective
        self.objective_copy = copy.copy(objective)
        self.last_commit_time = time.time()

    def init(self):
        if self.tuning_run is not None:
            return

        program_version = self.measurement_interface.db_program_version(self.session)
        self.session.flush()

        # --resume / --resume-uuid: continue an interrupted run.  Only fall
        # back to a fresh run when neither flag was given, or when --resume
        # found nothing to continue (an explicit --resume-uuid must match).
        if getattr(self.args, 'resume', False) or getattr(self.args, 'resume_uuid', None):
            self.tuning_run = self.find_resumable_tuning_run(program_version)

        if self.tuning_run is None:
            # prefix_hook() belongs to setting a brand new run up (and some
            # implementations exit early for their own analysis modes), so it
            # is deliberately not re-run when continuing one.
            self.measurement_interface.prefix_hook(self.session)
            self.tuning_run = resultsdb.models.TuningRun(
                uuid=uuid.uuid4().hex,
                name=self.args.label,
                args=self.args,
                start_date=datetime.now(),
                program_version=program_version,
                objective=self.objective_copy,
            )
            self.session.add(self.tuning_run)

        driver_kwargs = {
            'args': self.args,
            'input_manager': self.input_manager,
            'manipulator': self.manipulator,
            'measurement_interface': self.measurement_interface,
            'objective': self.objective,
            'session': self.session,
            'tuning_run_main': self,
            'tuning_run': self.tuning_run,
            'extra_seeds': self.measurement_interface.seed_configurations(),
            'extra_criteria': self.measurement_interface.extra_convergence_criteria
        }

        self.search_driver = self.search_driver_cls(**driver_kwargs)
        self.measurement_driver = self.measurement_driver_cls(**driver_kwargs)
        self.measurement_interface.set_driver(self.measurement_driver)
        self.input_manager.set_driver(self.measurement_driver)
        self.tuning_run.machine_class = self.measurement_driver.get_machine_class()
        self.tuning_run.input_class = self.input_manager.get_input_class()

    def find_resumable_tuning_run(self, program_version):
        """
        Return the TuningRun --resume / --resume-uuid asks for, or None.

        A run counts as resumable while its state is not COMPLETE: a run
        killed by SIGINT/Reboot is left ABORTED (or RUNNING when the process
        died without unwinding), and either way its recorded results are
        still valid, so the search just continues where it stopped.
        """
        tuning_run_cls = resultsdb.models.TuningRun

        if self.args.resume_uuid:
            tuning_run = (self.session.query(tuning_run_cls)
                          .filter_by(uuid=self.args.resume_uuid).first())
            if tuning_run is None:
                raise ValueError('--resume-uuid: no TuningRun with uuid %r in %s'
                                 % (self.args.resume_uuid, self.args.database))
            if tuning_run.state == 'COMPLETE':
                log.warning('TuningRun %s is already COMPLETE, resuming anyway',
                            tuning_run.uuid)
        else:
            tuning_run = (self.session.query(tuning_run_cls)
                          .filter(tuning_run_cls.program_version == program_version)
                          .filter(tuning_run_cls.name == self.args.label)
                          .filter(tuning_run_cls.state != 'COMPLETE')
                          .order_by(tuning_run_cls.start_date.desc())
                          .first())
            if tuning_run is None:
                log.warning('--resume: no unfinished TuningRun labelled %r, '
                            'starting a new one', self.args.label)
                return None

        log.info('resuming TuningRun %s (label=%r, state=%s, started %s)',
                 tuning_run.uuid, tuning_run.name, tuning_run.state,
                 tuning_run.start_date)
        tuning_run.state = 'RUNNING'
        tuning_run.end_date = None
        self.session.flush()
        return tuning_run

    def commit(self, force=False):
        if force or not self.fake_commit or time.time() - self.last_commit_time > 30:
            self.session.commit()
            self.last_commit_time = time.time()
        else:
            self.session.flush()

    def main(self):
        self.init()
        try:
            self.tuning_run.state = 'RUNNING'
            self.commit(force=True)
            self.search_driver.main()
            if self.search_driver.best_result:
                self.measurement_interface.save_final_config(self.search_driver.best_result.configuration)
            self.tuning_run.final_config = self.search_driver.best_result.configuration
            self.tuning_run.state = 'COMPLETE'
        except:
            self.tuning_run.state = 'ABORTED'
            raise
        finally:
            self.tuning_run.end_date = datetime.now()
            self.commit(force=True)
            self.session.close()

    def results_wait(self, generation):
        self.measurement_interface.pre_process()
        self.measurement_driver.process_all()
        self.measurement_interface.post_process()


def main(interface, args, *pargs, **kwargs):
    if inspect.isclass(interface):
        interface = interface(args=args, *pargs, **kwargs)
    return TuningRunMain(interface, args).main()
