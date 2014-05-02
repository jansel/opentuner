from opentuner.search import technique
import math
import random
#Default interval steps for cooling schedules
DEFAULT_INTERVAL = 100

#Pseudo-annealing - no relative energy input into acceptance function
class PseudoAnnealingSearch(technique.SequentialSearchTechnique):
  def __init__(self,
               temps = [30,0], #temperature schedule
               intervals = [],  #duration schedule
          		 loop = True, #Do we loop the schedule if we reach the end?
               *pargs, **kwargs):
    #fill intervals sufficiently
    ext_intervals = list(intervals)
    for i in range(len(temps)-len(intervals)-1):
      ext_intervals.append(DEFAULT_INTERVAL)
            
    #create temperature schedule (list of temps)
    cool_schedule = [temps[0]]
    for i in range(len(temps)-1):
      step = (float(temps[i+1]) - temps[i])/ext_intervals[i]
      for j in range(ext_intervals[i]):
        cool_schedule.append(max(cool_schedule[-1] + step,0))
      
    self.cool_schedule = cool_schedule
    self.loop = loop
    self.scaling = 50 #scaling of acceptance function
      
    super(PseudoAnnealingSearch,self).__init__(*pargs,**kwargs)


  def main_generator(self):
    objective = self.objective
    driver = self.driver
    manipulator = self.manipulator

    #Start in a random spot
    state = driver.get_configuration(manipulator.random())
    yield state
    #schedule counter
    counter = 0
    max_time = len(self.cool_schedule)-1
    #Check whether relative objective implemented
    has_rel = objective.relative(state,state) is not None
    has_rel=False
              
    while True:
      #Determine temperature
      temp = self.cool_schedule[min(counter,max_time)]
      #scale stepsize with temp and time (arbitrary)
      step_size = math.exp(-(20 + counter/100)/(temp+ 1)) 
          
      #get candidate neighbors using manipulator
      points = list()
      points.append(state)
      for param in manipulator.parameters(state.data):
        if param.is_primitive():
          # get current value of param, scaled to be in range [0.0, 1.0]
          unit_value = param.get_unit_value(state.data)
          if unit_value > 0.0:
            # produce new config with param set step_size lower
            down_cfg = manipulator.copy(state.data)
            param.set_unit_value(down_cfg, max(0.0, unit_value - step_size*random.random()))
            down_cfg = driver.get_configuration(down_cfg)
            self.yield_nonblocking(down_cfg)
            points.append(down_cfg)

          if unit_value < 1.0:
            # produce new config with param set step_size higher
            up_cfg = manipulator.copy(state.data)
            param.set_unit_value(up_cfg, min(1.0, unit_value + step_size*random.random()))
            up_cfg = driver.get_configuration(up_cfg)
            self.yield_nonblocking(up_cfg)
            points.append(up_cfg)
        else: # ComplexParameter
          for mutate_function in param.manipulators(state.data):
            cfg = manipulator.copy(state.data)
            mutate_function(cfg)
            cfg = driver.get_configuration(cfg)
            self.yield_nonblocking(cfg)
            points.append(cfg)
      yield None # wait for all results
            
      #Relative comparison implemented
      if has_rel:
        while True:
          if len(points) == 0:
            state = driver.best_result.configuration
            break
          candidate = points.pop(random.randint(0,len(points)-1))
          #compare to global best
          if random.random() < AcceptanceFunction(1, objective.relative(candidate,driver.best_result.configuration), temp, self.scaling):
            state = candidate
            break
      #No relative compare
      else:
      #sort points by "energy" (quality)
        points.sort(cmp=objective.compare)
            
        #Make decision about changing state
        #probability picking next-best state is exp^(-1/temp)
        #repeat and cycle to get state p-dist resembling this
        sel = 0
        while AcceptanceFunction(0,1,temp,1)>random.random():
          sel += 1
        state = points[sel%len(points)]
            
        #switch to the global best if temperature is low (i.e. we aren't moving much)
        if AcceptanceFunction(0,1,temp,1)< .0001 and objective.lt(driver.best_result.configuration, state):
          state = driver.best_result.configuration
          
      #update counter
      counter +=1
      if counter>max_time and self.loop:
        counter=counter-max_time
              

#Acceptance probability function for annealing
def AcceptanceFunction(e,e_new,temp,scaling):
  #Standard acceptance probability function using relative "goodness"
  if e>=e_new:
    return 1
  if temp == 0:
    return 0
  if scaling*(e_new-e)/temp > 10:
    #for practical purposes, probability is too low.
    return 0
  return math.exp(scaling*(e-e_new)/temp)


#register technique
technique.register(PseudoAnnealingSearch())
