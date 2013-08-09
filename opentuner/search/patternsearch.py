

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




