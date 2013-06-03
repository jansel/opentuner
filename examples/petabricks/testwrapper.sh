#!/bin/bash
COUNT=50
for Z in `seq $COUNT`
do
  for T in `./pbtuner.py --list-techniques $@`;
  do
    echo $Z/$COUNT $T
    ./pbtuner.py --technique=$T $@
  done
done

