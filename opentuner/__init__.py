
import search, measurement, tuningrunmain

def argparsers():
  '''
  return a list of ArguementParser to be used as parents to the user's 
  '''
  return [
      measurement.driver.argparser,
      search.driver.argparser,
      tuningrunmain.argparser,
    ]

