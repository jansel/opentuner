
from __future__ import absolute_import
import sys
from os.path import normpath, realpath, dirname, join, isfile

project_root = normpath(join(dirname(realpath(__file__)), '../..'))

if 'venv' not in ','.join(sys.path):
  venv_activate = join(project_root, 'venv/bin/activate_this.py')
  if isfile(venv_activate):
    exec(compile(open(venv_activate).read(), venv_activate, 'exec'), dict(__file__=venv_activate))

sys.path.insert(0, project_root)

