OpenTuner
=========

Program autotuning has been demonstrated in many domains to achieve better
or more portable performance.  However, autotuners themselves are often not
very portable between projects because using a domain informed search space
representation is critical to achieving good results and because no single
search technique performs best for all problems.

OpenTuner is a new framework for building domain-specific multi-objective
program autotuners. OpenTuner supports fully customizable configuration
representations, an extensible technique representation to allow for
domain-specific techniques, and an easy to use interface for communicating
with the tuned program. A key capability inside OpenTuner is the use of
ensembles of disparate search techniques simultaneously, techniques which
perform well will receive larger testing budgets and techniques which perform
poorly will be disabled.

System dependencies
-------------------

A list of system dependencies can be found in [debian-package-deps][]
which are primarily python 2.6+ (not 3.x) and sqlite3 (or your
[supported][sqlalchemy-dialects] database backend of choice).

On Ubuntu/Debian there can be installed with:

    sudo apt-get install `cat debian-package-deps`

[debian-package-deps]: https://raw.github.com/jansel/opentuner/master/debian-packages-deps
[sqlalchemy-dialects]: http://docs.sqlalchemy.org/en/rel_0_8/dialects/index.html

Python dependencies
------------------

A list of python dependencies can be found in [python-packages][] these can
either be installed system-wide with `pip` or `easy_install`, or you can
use virtual env to create a isolated python environment by running:

    python ./venv-bootstrap.py

which will create a ./venv/bin/python with all the required packages installed.

[python-packages]: https://raw.github.com/jansel/opentuner/master/python-packages

Tutorials
-------------

- A tutorial for creating new techniques can be found [here][technique-tutorial].

More coming soon!

[technique-tutorial]:  https://github.com/jansel/opentuner/wiki/TechniqueTutorial




