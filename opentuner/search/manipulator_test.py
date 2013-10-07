from manipulator import *

m = ConfigurationManipulator([PermutationParameter('tsp', range(5)),
                              FloatParameter('float', -10, 10)])
p, f, = m.params[:2]

import random
r = random.Random()
cfg1 = m.random()
cfg2 = m.random()
p1=[14, 9, 12, 3, 0, 5, 8, 2, 7, 6, 4, 10, 1, 11, 13]
p2=[6, 7, 13, 2, 11, 9, 5, 3, 0, 10, 12, 4, 14, 8, 1]
cfg1['tsp']=p1
cfg2['tsp']=p2

##print p.PMX(cfg1, cfg2)
##for i in range(50):
##
##
##    print cfg1, cfg2
##    ##print p.PX(cfg1, cfg2, 3, 4)
##    cfg1, cfg2 = p.PMX(cfg1, cfg2)
    



                     
