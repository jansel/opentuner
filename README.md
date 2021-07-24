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


Installation
-------------------

OpenTuner requires python 3.7+ and sqlite3 (or your
[supported][sqlalchemy-dialects] database backend of choice).
Install with:

    sudo pip install opentuner

or

    pip install --user opentuner

[sqlalchemy-dialects]: http://docs.sqlalchemy.org/en/rel_0_8/dialects/index.html

Development installation
-------------------

For development or running examples out of a git checkout, we recommend using
[miniconda3](https://docs.conda.io/en/latest/miniconda.html).

    conda create --name=opentuner python=3.8
    conda activate opentuner
    pip install -r requirements.txt -r optional-requirements.txt
    python setup.py develop


Checking Installation
---------------------

To check an installation you can run tests:

    pytest tests/*

Or run an example program:

    ./examples/rosenbrock/rosenbrock.py


Tutorials
---------

- [Optimizing Block Matrix Multiplication][gettingstarted]
- [Creating OpenTuner Techniques][technique-tutorial].

[gettingstarted]: http://opentuner.org/tutorial/gettingstarted/
[technique-tutorial]:  http://opentuner.org/tutorial/techniques/


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
on github and [submit a pull request][pull-req].

[pull-req]: https://www.openshift.com/wiki/github-workflow-for-submitting-pull-requests


Support
-------
OpenTuner is supported in part by the United States Department of Energy
[X-Stack][xstack] program as part of [D-TEC][dtec].

[xstack]: http://science.energy.gov/ascr/research/computer-science/ascr-x-stack-portfolio/
[dtec]: http://www.dtec-xstack.org/

