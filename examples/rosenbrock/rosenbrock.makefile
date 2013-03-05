#!/usr/bin/make -f
# use -j4 to run in parallel

TECHNIQUES := $(shell ./rosenbrock.py --list-techniques)
define test_loop
DB="sqlite:///$$FN$$DIMS.db";           \
for N in `seq 30`; do                   \
	for TEQ in $(TECHNIQUES); do          \
		./rosenbrock.py --function=$$FN     \
										--technique=$$TEQ   \
										--dimensions=$$DIMS \
										--database=$$DB;    \
	done;                                 \
done;
endef

default: rosenbrock2 rosenbrock4 sphere baele

rosenbrock2:
	FN=rosenbrock; DIMS=2; $(test_loop)

rosenbrock4:
	FN=rosenbrock; DIMS=4; $(test_loop)

rosenbrock8:
	FN=rosenbrock; DIMS=8; $(test_loop)

sphere:
	FN=sphere;     DIMS=4; $(test_loop)

baele:
	FN=beale;      DIMS=2; $(test_loop)

