#!/usr/bin/make -f
# use -j4 to run in parallel

FN         := rosenbrock
DIMS       := 4
TECHNIQUES := $(shell ./rosenbrock.py --list-techniques)
define test_loop
DB="sqlite:///opentuner.db/$$RUN.db";     \
for TEQ in $(TECHNIQUES); do          \
	./rosenbrock.py --function=$(FN)    \
									--technique=$$TEQ  \
									--dimensions=$(DIMS)   \
									--database=$$DB;       \
done;
endef

default: run.1 run.2 run.3 run.4 run.5 run.6 run.7 run.8 run.9 run.10 run.11 \
run.12 run.13 run.14 run.15 run.16 run.17 run.18 run.19 run.20 run.21 run.22 \
run.23 run.24 run.25 run.26 run.27 run.28 run.29 run.30

run.%:
	RUN=$* $(test_loop)


