---
layout: default
title: OpenTuner - An extensible framework for program autotuning
permalink: /index.html
---

About OpenTuner
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

News
-------

We will be giving another [OpenTuner tutorial](/tutorial/pldi2015/) at
[PLDI 2015](http://conf.researchr.org/home/pldi2015).  PLDI will take place
in Portland, Oregon on June 13-17 2015.  The OpenTuner tutorial will be on
the afternoon of Sunday, June 14th.

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


