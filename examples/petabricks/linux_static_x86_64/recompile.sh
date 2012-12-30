#!/bin/sh

DST=`pwd`

#this is hardcoded, you should change it :)
cd ~/petabricks

./configure CXXFLAGS="-O2 -static"
make

./pbrun kmeans
cp ./examples/kclustering/kmeans $DST/

./pbrun Sort2
cp ./examples/sort2/Sort2 $DST/

#there are two "Convolution.pbcc" files, need to specify exactly
./pbrun ./examples/convolution2/Convolution
cp ./examples/convolution2/Convolution $DST/Convolution2

./pbrun strassen
cp ./examples/multiply/strassen $DST/

./pbrun TriSolve
cp ./examples/trisolve/TriSolve $DST/

cd $DST
for X in Convolution2 kmeans Sort2 strassen TriSolve
do
  ./$X --config=$X.cfg.default --reset
done

