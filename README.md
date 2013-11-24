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

A list of system dependencies can be found in [debian-packages-deps][]
which are primarily python 2.6+ (not 3.x) and sqlite3 (or your
[supported][sqlalchemy-dialects] database backend of choice).

On Ubuntu/Debian there can be installed with:

    sudo apt-get install `cat debian-packages-deps | tr '\n' ' '`

[debian-packages-deps]: https://raw.github.com/jansel/opentuner/master/debian-packages-deps
[sqlalchemy-dialects]: http://docs.sqlalchemy.org/en/rel_0_8/dialects/index.html

Python dependencies
-------------------

A list of python dependencies can be found in [python-packages][] these can
either be installed system-wide with `pip` or `easy_install`.

    sudo apt-get install python-pip
    sudo pip install -r python-packages

Or you can use virtual env to create a isolated python environment by running:

    python ./venv-bootstrap.py

which will create a ./venv/bin/python (./venv/Scripts/python.exe on windows)
with all the required packages installed.

[python-packages]: https://raw.github.com/jansel/opentuner/master/python-packages

Checking Installation
---------------------

Quickly checking that a successful installation has been made, may be performed
by running an example program such as:

    cd examples/gccflags/
    ./gccflags_minimal.py

Tutorials
---------

- A tutorial for creating new techniques can be found [here][technique-tutorial].

More coming soon!

[technique-tutorial]:  https://github.com/jansel/opentuner/wiki/TechniqueTutorial


Papers
---------

- [OpenTuner: An Extensible Framework for Program Autotuning][techreport1]. <br>
  Jason Ansel, Shoaib Kamil, Kalyan Veeramachaneni, Una-May O'Reilly,  Saman Amarasinghe. <br>
  MIT CSAIL Technical Report MIT-CSAIL-TR-2013-026.
  November 1, 2013.

[techreport1]: http://dspace.mit.edu/handle/1721.1/81958


Contributing Code
-----------------

The preferred way to contribute code to OpenTuner is to fork the project
on github and [submit a pull request][pull-req].  You can also submit a
[patch via email][email-patch] to jansel@csail.mit.edu.

[pull-req]: https://www.openshift.com/wiki/github-workflow-for-submitting-pull-requests
[email-patch]: http://alblue.bandlem.com/2011/12/git-tip-of-week-patches-by-email.html

