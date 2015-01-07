OpenTuner Tutorial @ CGO 2015
=======================

We will be giving a [tutorial][tutorialsite] at [CGO 2015][cgo2015].
CGO will take place at the San Francisco Airport Marriott Waterfront and
the OpenTuner tutorial will be on Sunday morning, Feb 8th 2015.

- [Early Registration Deadline][cgoreg]: Jan 11, 2015
- [Hotel Reservation Cut-off][cgohotel]: Jan 16, 2015
- More information on the [CGO website][cgo2015]

[cgoreg]: https://www.regonline.com/cgo2015
[cgohotel]: https://aws.passkey.com/g/40122128
[cgo2015]: http://cgo.org/cgo2015/
[tutorialsite]: http://opentuner.org/tutorial/cgo2015/

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


Tutorials
---------

- A tutorial for creating new techniques can be found [here][technique-tutorial].

More coming soon!

[technique-tutorial]:  https://github.com/jansel/opentuner/wiki/TechniqueTutorial


Papers
---------

- [OpenTuner: An Extensible Framework for Program Autotuning][paper1]. <br>
  Jason Ansel, Shoaib Kamil, Kalyan Veeramachaneni, Jonathan Ragan-Kelley,
  Jeffrey Bosboom, Una-May O'Reilly, Saman Amarasinghe. <br>
  International Conference on Parallel Architectures and Compilation
  Techniques. <br>
  Edmonton, Canada. August, 2014. [Slides][slides1]. [Bibtex][bibtex1].

[paper1]: http://groups.csail.mit.edu/commit/papers/2014/ansel-pact14-opentuner.pdf
[bibtex1]: http://groups.csail.mit.edu/commit/bibtex.cgi?key=ansel:pact:2014
[slides1]: http://groups.csail.mit.edu/commit/papers/2014/ansel-pact14-opentuner-slides.pdf


Contributing Code
-----------------

The preferred way to contribute code to OpenTuner is to fork the project
on github and [submit a pull request][pull-req].  You can also submit a
[patch via email][email-patch] to jansel@csail.mit.edu.

[pull-req]: https://www.openshift.com/wiki/github-workflow-for-submitting-pull-requests
[email-patch]: http://alblue.bandlem.com/2011/12/git-tip-of-week-patches-by-email.html


Support
-------
OpenTuner is supported in part by the United States Department of Energy
[X-Stack][xstack] program as part of [D-TEC][dtec].

[xstack]: http://science.energy.gov/ascr/research/computer-science/ascr-x-stack-portfolio/
[dtec]: http://www.dtec-xstack.org/


