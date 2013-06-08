#!/bin/sh

DST=`pwd`

#this is hardcoded, you should change it :)
cd /data/commit/jansel/petabricks

./configure CXXFLAGS="-O2"
make

for X in ./examples/multigrid/Poisson2DFMG ./examples/multigrid/Helmholtz3DFMG
do
  ./pbrun $X
  cp $X $DST/
done

cd $DST
for X in Poisson2DFMG Helmholtz3DFMG
do
  ./$X --config=$X.cfg.default --reset
done

