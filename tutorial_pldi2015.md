---
layout: default
title: OpenTuner - Tutorial at CGO 2015
permalink: /tutorial/pldi2015/index.html
redirect_from: /tutorial/cgo2015/index.html
---

Tutorial at PLDI 2015
=================

We will be giving another [OpenTuner tutorial](/tutorial/pldi2015/) at
[PLDI 2015](http://conf.researchr.org/home/pldi2015).  PLDI will take place
in Portland, Oregon on June 13-17 2015.  The OpenTuner tutorial will be in
the afternoon on Sunday, June 14th.

We also gave this tutorial at the [2015 International Symposium on Code
Generation and Optimization][cgo2015] (CGO) on February 8th, 2015.

[cgo2015]: http://cgo.org/cgo2015/


Brief Tutorial Description
------

This tutorial will cover the usage of OpenTuner, a open source framework
for building domain-specific multi-objective program autotuners.  OpenTuner
supports fully customizable configuration representations, an extensible
technique representation to allow for domain-specific techniques, and
an easy to use interface for communicating with the tuned program. A key
capability inside OpenTuner is the use of ensembles of disparate search
techniques simultaneously.  Techniques which perform well will receive
larger testing budgets and techniques which perform poorly will be disabled.
OpenTuner has been used by a number of different projects to build domain
specific autotuners.

The topics covered in the workshop will be:

  - Overview of autotuning: including a history of past autotuning projects
  and how autotuning is used today

  - Machine learning primer: empirical search, model based techniques,
  and which technique is right for you

  - OpenTuner framework: how is it designed and how you should use it

  - Examples of using OpenTuner

  - What makes a good search space representation: the secret sauce of
  autotuning

  - How to go about autotuning your system with OpenTuner

  - Hands-on session with OpenTuner

Agenda
------

Note that the speakers and slides are from the version of the tutorial at
CGO and may change for the PLDI version.

- [Welcome and broader context](/slides/opentuner-cgo2015-amarasinghe-welcome.pdf)
  (Saman Amarasinghe)

- [Introduction to OpenTuner](/slides/opentuner-cgo2015-ansel-opentuner-intro.pdf)
  (Jason Ansel)

- [Search techniques](/slides/opentuner-cgo2015-veeramachaneni-ml.pdf)
  (Kalyan Veeramachaneni)

- [In depth example](/slides/opentuner-cgo2015-bosboom-in-depth.pdf)
  (Jeffrey Bosboom)

- Break

- Applications

    - [Halide](/slides/opentuner-cgo2015-jrk-halide.pdf) (Jonathan Ragan-Kelley)
    - [SEJITS](/slides/opentuner-cgo2015-markley-sejits.pdf) (Chick Markley)
    - [JVM optimization](/slides/opentuner-cgo2015-rusira-jvm-opt.pdf) (Tharindu Rusira)

- [Hands on session](/slides/opentuner-cgo2015-hands-on.pdf) (Shoaib Kamil)
  - _Requires a thumb drive with a virtual machine distributed at the tutorial_

- Discussion

