---
layout: default
title: OpenTuner - Technique Tutorial
permalink: /tutorial/techniques/index.html
---

Creating OpenTuner Techniques
==========================

This tutorial will walk through the basics of adding a new search
technique to OpenTuner.  We will add the technique pattern search (see
<http://en.wikipedia.org/wiki/Pattern_search_(optimization)>).  If you do
not already have OpenTuner running on your system you should first do the
[initial setup](/tutorial/setup/).

## Initial Version

Store the following file in `opentuner/opentuner/search/my_technique.py`, or in the directory for your project:

    from opentuner.search import technique

    class BasicPatternSearch(technique.SequentialSearchTechnique):
      def main_generator(self):

        objective   = self.objective
        driver      = self.driver
        manipulator = self.manipulator

        # start at a random position
        center = driver.get_configuration(manipulator.random())
        yield center

        # initial step size is arbitrary
        step_size = 0.1

        while True:
          points = list()
          for param in manipulator.parameters(center.data):
            if param.is_primitive():
              # get current value of param, scaled to be in range [0.0, 1.0]
              unit_value = param.get_unit_value(center.data)

              if unit_value > 0.0:
                # produce new config with param set step_size lower
                down_cfg = manipulator.copy(center.data)
                param.set_unit_value(down_cfg, max(0.0, unit_value - step_size))
                down_cfg = driver.get_configuration(down_cfg)
                yield down_cfg
                points.append(down_cfg)

              if unit_value < 1.0:
                # produce new config with param set step_size higher
                up_cfg = manipulator.copy(center.data)
                param.set_unit_value(up_cfg, min(1.0, unit_value + step_size))
                up_cfg = driver.get_configuration(up_cfg)
                yield up_cfg
                points.append(up_cfg)

          #sort points by quality, best point will be points[0], worst is points[-1]
          points.sort(cmp=objective.compare)

          if objective.lt(points[0], center):
            # we found a better point, move there
            center = points[0]
          else:
            # no better point, shrink the pattern
            step_size /= 2.0

    # register our new technique in global list
    technique.register(BasicPatternSearch())

### Code explanation

Going through this example in some more detail:

      def main_generator(self):

The main_generator() is the central function for the SequentialSearchTechnique model (note there are some other technique models which support more parallelism in running tests).  It should yield opentuner.resultsdb.models.Configuration objects, at which point the technique will block until results are ready for the yielded configuration.

        objective   = self.objective

The objective object (defined in `opentuner/opentuner/search/objective.py`) is used to compare configurations using a user defined quality metrics.  It is typically an instance of MinimizeTime() which only looks at the time value of result objects, but may be something more complex such as ThresholdAccuracyMinimizeTime().

        driver      = self.driver

The search driver object (defined in `opentuner/opentuner/search/driver.py`) is used for interacting with the results database.  It can be used to query results both for configurations requested by this technique and other techniques.

        manipulator = self.manipulator

The configuration manipulator object (defined in `opentuner/opentuner/search/manipulator.py`) allows the technique to make changes and examine configurations.  Conceptually it is a list of parameter objects which are either primitive and have function such as `set_value` / `get_value` / `legal_range` or complex with a set of opaque manipulator functions that will change the underlying config.

        # start at a random position
        center = driver.get_configuration(manipulator.random())

`manipulator.random()` will return a random raw configuration (usually of type `dict`).  `driver.get_configuration` will convert this to a `opentuner.resultdb.models.Configuration` database record by either inserting it into the database if it is a new configuration, or looking up an existing object if it has been queried before.  After this conversion the configuration is now immutable, and has been assigned an id which will be used to lookup results for it.

        yield center

          for param in manipulator.parameters(center.data):

This will use the manipulator to iterator over the `opentuner.manipulator.Parameter` objects for this configuration.

            if param.is_primitive():

For this initial version we will only handle
`opentuner.manipulator.PrimitiveParameter` objects, which are based on
`set_value`, `get_value`, and `legal_range` functions.

              # get current value of param, scaled to be in range [0.0, 1.0]
              unit_value = param.get_unit_value(center.data)

We will use the convenience functions `get_unit_value` and `set_unit_value` which scale the parameter into a float from 0.0 to 1.0.  `set_unit_value` will perform rounding for us if the underlying type is an integer.

              if unit_value > 0.0:
                # produce new config with param set step_size lower
                down_cfg = manipulator.copy(center.data)

We copy `center.data` to get a mutable object to create our new configuration with.  `down_cfg` is now a raw configuration, typically of type `dict`.

                param.set_unit_value(down_cfg, max(0.0, unit_value - step_size))

Use the parameter to mutate `down_cfg` to have the value of param be `step_size` lower.

                down_cfg = driver.get_configuration(down_cfg)
                yield down_cfg

Same as before, `driver.get_configuration` will convert the raw mutable configuration to a immutable `opentuner.resultdb.models.Configuration` database record which we can use to query for results.  This then waits for results to be ready.

          #sort points by quality, best point will be points[0], worst is points[-1]
          points.sort(cmp=objective.compare)

          if objective.lt(points[0], center):
            # we found a better point, move there
            center = points[0]
          else:
            # no better point, shrink the pattern
            step_size /= 2.0

Finally we use `objective.compare` and `objective.lt` to decide to either move the pattern or shrink the pattern depending on if we found a better configuration.

    # register our new technique in global list
    technique.register(BasicPatternSearch())

This registers our technique in the global list to allow it to be selected with the `--technique=BasicPatternSearch` command line flag.

## Running the new technique

Run the newly created technique, you need a program to tune.  Some examples can be found in the `opentuner/examples` directory.  The most simple is `opentuner/examples/rosenbrock` which implements a subset of the test functions described at <http://en.wikipedia.org/wiki/Test_functions_for_optimization>.

    ~/opentuner/examples/rosenbrock$ ./rosenbrock.py --technique=BasicPatternSearch --function=sphere --display-frequency=1 --test-limit=100
    [     1s]    INFO opentuner.search.plugin.DisplayPlugin: tests=17, best time=52.6332 acc=nan, found by BasicPatternSearch
    [     2s]    INFO opentuner.search.plugin.DisplayPlugin: tests=42, best time=1.6837 acc=nan, found by BasicPatternSearch
    [     3s]    INFO opentuner.search.plugin.DisplayPlugin: tests=67, best time=0.0049 acc=nan, found by BasicPatternSearch
    [     4s]    INFO opentuner.search.plugin.DisplayPlugin: tests=92, best time=0.0000 acc=nan, found by BasicPatternSearch
    [     5s]    INFO opentuner.search.plugin.DisplayPlugin: tests=101, best time=0.0000 acc=nan, found by BasicPatternSearch
    ~/opentuner/examples/rosenbrock$

The most important argument here is `--technique=BasicPatternSearch` which selects our newly added technique as the one to use.

## Improved version

The following is a improved version of PatternSearch

    from opentuner.search import technique

    class PatternSearch(technique.SequentialSearchTechnique):
      def main_generator(self):

        objective   = self.objective
        driver      = self.driver
        manipulator = self.manipulator

        # start at a random position
        center = driver.get_configuration(manipulator.random())
        self.yield_nonblocking(center)

        # initial step size is arbitrary
        step_size = 0.1

        while True:
          points = list()
          for param in manipulator.parameters(center.data):
            if param.is_primitive():
              # get current value of param, scaled to be in range [0.0, 1.0]
              unit_value = param.get_unit_value(center.data)

              if unit_value > 0.0:
                # produce new config with param set step_size lower
                down_cfg = manipulator.copy(center.data)
                param.set_unit_value(down_cfg, max(0.0, unit_value - step_size))
                down_cfg = driver.get_configuration(down_cfg)
                self.yield_nonblocking(down_cfg)
                points.append(down_cfg)

              if unit_value < 1.0:
                # produce new config with param set step_size higher
                up_cfg = manipulator.copy(center.data)
                param.set_unit_value(up_cfg, min(1.0, unit_value + step_size))
                up_cfg = driver.get_configuration(up_cfg)
                self.yield_nonblocking(up_cfg)
                points.append(up_cfg)

            else: # ComplexParameter
              for mutate_function in param.manipulators(center.data):
                cfg = manipulator.copy(center.data)
                mutate_function(cfg)
                cfg = driver.get_configuration(cfg)
                self.yield_nonblocking(cfg)
                points.append(cfg)


          yield None # wait for all results

          #sort points by quality, best point will be points[0], worst is points[-1]
          points.sort(cmp=objective.compare)

          if (objective.lt(driver.best_result.configuration, center)
              and driver.best_result.configuration != points[0]):
            # another technique found a new global best, switch to that
            center = driver.best_result.configuration
          elif objective.lt(points[0], center):
            # we found a better point, move there
            center = points[0]
          else:
            # no better point, shrink the pattern
            step_size /= 2.0

    # register our new technique in global list
    technique.register(PatternSearch())

There are three main changes:

### Yield_nonblocking for parallelism

        ...
        self.yield_nonblocking(center)
        ...
                self.yield_nonblocking(down_cfg)
        ...
                self.yield_nonblocking(up_cfg)
        ...
          yield None # wait for all results

This change allows tests to run in parallel. `self.yield_nonblocking(cfg)` requests that cfg be tested, but does not wait for the results.  `yield None` waits for all prior `yield_nonblocking` result requests, and must be done before the configurations are compared against each other with `objective`.

### Support ComplexParameters

            else: # ComplexParameter
              for mutate_function in param.manipulators(center.data):
                cfg = manipulator.copy(center.data)
                mutate_function(cfg)
                cfg = driver.get_configuration(cfg)
                self.yield_nonblocking(cfg)
                points.append(cfg)

This change adds support for ComplexParamers which do not have a linear value, but instead have a set of opaque manipulator functions.  We simply add one point to points for each manipulator function.

### Sharing information with other techniques

          if (objective.lt(driver.best_result.configuration, center)
              and driver.best_result.configuration != points[0]):
            # another technique found a new global best, switch to that
            center = driver.best_result.configuration

Since we may want to run this technique with other techniques, this change makes use of progress made by other techniques.  If another technique found a better configuration, we switch to that new global best and abandon the current position.
