
import measurement
import resultsdb
import search
import tuningrunmain
from opentuner.measurement import MeasurementInterface
from opentuner.resultsdb.models import Configuration
from opentuner.resultsdb.models import DesiredResult
from opentuner.resultsdb.models import Result
from opentuner.resultsdb.models import TuningRun
from opentuner.search.manipulator import ConfigurationManipulator
from opentuner.search.manipulator import EnumParameter
from opentuner.search.manipulator import FloatParameter
from opentuner.search.manipulator import IntegerParameter
from opentuner.search.manipulator import LogFloatParameter
from opentuner.search.manipulator import LogIntegerParameter
from opentuner.search.manipulator import PermutationParameter
from opentuner.search.manipulator import ScheduleParameter
from opentuner.search.manipulator import SwitchParameter
from opentuner.tuningrunmain import init_logging


def argparsers():
  """
  return a list of ArguementParser to be used as parents to the user's
  """
  return [
      measurement.driver.argparser,
      measurement.interface.argparser,
      search.driver.argparser,
      search.plugin.argparser,
      search.technique.argparser,
      #stats.argparser,
      tuningrunmain.argparser,
    ]


def default_argparser():
  import argparse
  return argparse.ArgumentParser(parents=argparsers())

