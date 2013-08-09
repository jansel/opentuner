#!/bin/bash
COUNT=50
for Z in `seq $COUNT`
do
  for T in `./unitary.py --list-techniques $@`;
  do
    echo $Z/$COUNT $T
    ./unitary.py --technique=$T $@
  done
done

