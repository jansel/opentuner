#!./venv/bin/python

extra = '''

default_target_dir = 'venv'

pip_install_packages = [
    'sqlalchemy',
    'pysqlite',
#   'lxml',
    'virtualenv',
    'fn',
    'psycopg2',
  ]

import os
import subprocess

def adjust_options(options, args):
  if len(args)==0:
    os.chdir(os.path.dirname(__file__))
    args.append(default_target_dir)

def after_install(options, home_dir):
  from os.path import join
  pip = join(home_dir, 'bin', 'pip')
  subprocess.call([pip, 'install'] + pip_install_packages)
# for prog in pip_install_packages:
#   subprocess.call([pip, 'install', prog])

'''

import os, virtualenv

os.chdir(os.path.dirname(__file__))
output = virtualenv.create_bootstrap_script(extra)
f = open('venv-bootstrap.py', 'w').write(output)

