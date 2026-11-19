# Resume an interrupted tuning run

This example shows that `--resume` continues the same `TuningRun` without
evaluating configurations a second time.

Run the three commands from this directory.  `PYTHONPATH=../..` makes them
use this checkout instead of an installed copy of OpenTuner (equivalently,
run `pip install -e ../..` once):

```bash
rm -f demo.db* resume-demo-measurements.jsonl resume-demo-state.json

# 1. Start a run and simulate a killed process after 6 measurements.
#    The process exits with a KeyboardInterrupt, leaving the run ABORTED.
PYTHONPATH=../.. python3 resume_demo.py --database sqlite:///demo.db \
    --label resume-demo --test-limit 12 --parallelism 1 \
    --interrupt-after 6 \
    --measure-log resume-demo-measurements.jsonl \
    --state-file resume-demo-state.json

# 2. Continue the same run.  Do not pass --interrupt-after this time.
PYTHONPATH=../.. python3 resume_demo.py --database sqlite:///demo.db \
    --label resume-demo --test-limit 12 --parallelism 1 --resume \
    --measure-log resume-demo-measurements.jsonl \
    --state-file resume-demo-state.json

# 3. Check the result.
PYTHONPATH=../.. python3 resume_demo.py --database sqlite:///demo.db \
    --test-limit 12 --verify \
    --measure-log resume-demo-measurements.jsonl \
    --state-file resume-demo-state.json
```

The last command prints `PASS` and checks, among other things:

* one `TuningRun` is `COMPLETE` and its uuid is the one recorded before the
  interruption,
* the run has exactly `--test-limit` requests in total, not
  `interrupted + test-limit`,
* each seed configuration has one request, and the duplicated seed shares
  the first request's `Result`,
* no configuration has more than one `Result`,
* the request the killed process left in state `RUNNING` was measured by the
  resumed process,
* the best result from before the interruption is still present.

An interrupt is simulated in `run()` instead of sending a real `SIGINT` so
the example is deterministic and works on every platform.  The state it
leaves behind (`RUNNING` `DesiredResult`, committed results) is the same.
