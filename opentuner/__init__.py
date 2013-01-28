
import search, measurement, tuningrunmain, stats

def argparsers():
  '''
  return a list of ArguementParser to be used as parents to the user's 
  '''
  return [
      tuningrunmain.argparser,
      search.driver.argparser,
      measurement.driver.argparser,
      stats.argparser,
    ]

