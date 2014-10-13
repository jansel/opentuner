---
layout: default
title: OpenTuner - Getting Started
permalink: /tutorial/setup/index.html
---

Getting Started with OpenTuner
===============

This page describes the installation of OpenTuner.

System dependencies
-------------------

A list of system dependencies can be found in [debian-packages-deps][]
which are primarily python 2.6+ (not 3.x) and sqlite3 (or your
[supported database backend][sqlalchemy-dialects] of choice).

On Ubuntu/Debian there can be installed with:

    sudo apt-get install `cat debian-packages-deps | tr '\n' ' '`

[debian-packages-deps]: https://raw.github.com/jansel/opentuner/master/debian-packages-deps
[sqlalchemy-dialects]: http://docs.sqlalchemy.org/en/rel_0_8/dialects/index.html


Installation
-------------------
OpenTuner (and dependencies) can be installed with

    sudo pip install opentuner

or

    pip install --user opentuner

This will not install any of the example programs.


Development installation
-------------------
For development (running OpenTuner out of a git checkout), a list of python
dependencies can be found in [requirements.txt][] these can either be
installed system-wide with `pip` or `easy_install`.

    sudo apt-get install python-pip
    sudo pip install -r requirements.txt

Or you can use virtual env to create a isolated python environment by running:

    python ./venv-bootstrap.py

which will create a ./venv/bin/python (./venv/Scripts/python.exe on windows)
with all the required packages installed.

[requirements.txt]: https://raw.github.com/jansel/opentuner/master/requirements.txt


Checking Installation
---------------------

Quickly checking that a successful installation has been made, may be performed
by running an example program such as:

    ./examples/rosenbrock/rosenbrock.py


