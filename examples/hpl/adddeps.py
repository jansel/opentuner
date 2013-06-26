
import sys
from os.path import normpath, realpath, dirname, join, isfile

proj_root = normpath(join(dirname(realpath(__file__)), '../..'))

if 'venv' not in ','.join(sys.path):
  venv_activate = join(proj_root, 'venv/bin/activate_this.py')
  if isfile(venv_activate):
    execfile(venv_activate, dict(__file__=venv_activate))

try:
  import opentuner
except:
  sys.path.append(proj_root)

