
import search, measurement, tuningrunmain
from tuningrunmain import main

def argparsers():
  '''
  return a list of ArguementParser to be used as parents to the user's 
  '''
  return [
      measurement.driver.argparser,
      search.driver.argparser,
      search.plugin.argparser,
      search.technique.argparser,
      #stats.argparser,
      tuningrunmain.argparser,
    ]

