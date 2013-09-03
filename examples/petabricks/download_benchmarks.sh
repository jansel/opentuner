#!/bin/sh
if test -e linux_x86_64
then
  echo "benchmarks already downloaded"
else
  wget -O- http://people.csail.mit.edu/jansel/petabricks_benchmarks_linux_x86_64.tar.bz2 | tar jxv
fi

