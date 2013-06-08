
import sys
from os.path import normpath, dirname, join, isfile

if 'venv' not in ','.join(sys.path):

  venv_activate = normpath(join(dirname(__file__),
                                '../../venv/bin/activate_this.py'))

  if isfile(venv_activate):
    execfile(venv_activate, dict(__file__=venv_activate))

try:
  import opentuner
except:
  sys.path.append(normpath(join(dirname(__file__), '../..')))

