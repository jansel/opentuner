#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Use OpenTuner to autotune CPython's GCC compile/link options, using
pyperformance as the objective.

How it works
------------
CPython's final compile command in the generated Makefile is::

    $(CC) ... $(BASECFLAGS) $(OPT) $(CONFIGURE_CFLAGS) $(CFLAGS) $(EXTRA_CFLAGS) ...
    $(CC) ... $(CONFIGURE_CFLAGS_NODIST) $(CFLAGS_NODIST) ...   # NODIST comes last

where:
* ``OPT``                       is set by ``--enable-optimizations`` and is
  effectively ``-DNDEBUG -g -fwrapv -O3 -Wall``;
* ``CONFIGURE_CFLAGS``          is whatever you pass via the ``CFLAGS``
  environment variable at configure time;
* ``CONFIGURE_LDFLAGS``         likewise comes from the ``LDFLAGS`` env var;
* ``CONFIGURE_CFLAGS_NODIST`` / ``CONFIGURE_LDFLAGS_NODIST`` hold flags
  appended by configure itself (``-fno-semantic-interposition -flto
  -fuse-linker-plugin -ffat-lto-objects -flto-partition=none``, etc.), driven
  by ``--with-lto``.

Because ``CONFIGURE_CFLAGS`` appears *after* ``OPT`` (``-O3``), putting ``-O2``
in ``CFLAGS`` really does override ``-O3``; likewise the ``-f`` / ``--param`` /
``-march`` options we tune are placed in ``CFLAGS`` before the NODIST part, so
they do not conflict with LTO/PGO.

Note: ``-fno-semantic-interposition`` and ``-flto-partition=none`` are already
appended to NODIST by ``--with-lto`` / ``--enable-optimizations`` and come
after the user CFLAGS, so they cannot be overridden via ``CFLAGS`` and are
intentionally left out of the search space.

``--enable-bolt`` (BOLT post-link optimization, new in CPython 3.12) is a
configure-level flag rather than a CFLAGS, so it is exposed as its own
``bolt`` parameter (on/off) and appended to the configure command. It requires
``llvm-bolt`` and ``merge-fdata`` on PATH.

For each configuration the tuner:
  1. builds a python3 out-of-tree via configure + make + make install;
  2. runs pyperformance on that interpreter using the host python;
  3. parses the pyperformance JSON output and scores the run as the geometric
     mean of all benchmark medians (lower is faster), which is returned to
     OpenTuner.

Usage
-----
    python3 cpython_pyperformance.py \\
        --source-dir ~/gerrit/cpython \\
        --build-root ./builds \\
        --pyperformance-python python3 \\
        --benchmarks 2to3,chameleon,django_template,json_loads,regex_compile \\
        --fast \\
        --jobs 16 \\
        --parallelism 1 \\
        --test-limit 200

Notes:
* ``--fast``            tell pyperformance to use fast mode (one value per
                        benchmark), greatly shortening each sample;
* ``--benchmarks``      run only a small representative subset of benchmarks;
* ``--test-limit N``    stop after N samples (in this fork it is a test count,
                        not a timeout); you can also use ``--stop-after SECONDS``
                        to stop by wall-clock time;
* ``--parallelism 1``   build one configuration at a time so parallel makes
                        don't thrash the CPU;
* with ``--fast`` the tuning ends with a final phase: the ``--topn N`` best
  configurations (default 5) are re-measured WITHOUT ``-f`` (full
  pyperformance mode), re-ranked by those full-mode scores and written to
  ``topn_results.json``; the champion reported in ``best_config.json`` /
  ``best_flags.sh`` comes from this full-mode ranking, so the reported
  improvement is reproducible in full-mode re-testing;
* a non-zero pyperformance exit does not discard a configuration when the
  result file still parses: pyperformance exits non-zero as soon as ONE
  benchmark dies, so the geomean over the surviving benchmarks is salvaged
  instead (benchmarks broken on the target interpreter, e.g. sympy 1.8
  importing distutils on 3.12, then cost a fixed set of missing entries
  rather than poisoning every configuration);
* per-configuration build/run timeouts are controlled by ``--build-timeout`` /
  ``--run-timeout`` (this fork's ``--test-limit`` is no longer a per-test
  timeout, see above);
* re-running after an interrupt does NOT resume by itself: every start
  creates a new ``TuningRun``, and the search begins from scratch even
  though earlier results stay in opentuner.db.  Pass ``--resume`` (with the
  same ``--label``) or ``--resume-uuid <uuid>`` to continue the interrupted
  run in place, keeping its test counter, generation and best result --
  requires the ``--resume`` support on top of upstream (see issue #117);
  without it, export the top-N configurations and re-seed them with
  ``--seed-configuration``;
* each configuration's dependencies go into its own venv, but pip hits the
  local cache (no repeated network download); the venv is removed after each
  run by default, use ``--keep-venv`` to keep it;
* the out-of-tree build artifacts (object files, generated sources) are removed
  right after each run, keeping only the installed interpreter and run logs so
  a re-measurement can reuse the cached build; once tuning completes the
  remaining ``build-<id>/`` directories are removed but the best
  configuration's installed interpreter is kept for the final comparison -- use
  ``--keep-builds`` to keep them all.
"""

from __future__ import print_function

import json
import logging
import math
import os
import re
import shlex
import shutil

import opentuner
from opentuner import ConfigurationManipulator
from opentuner import EnumParameter
from opentuner import IntegerParameter
from opentuner import MeasurementInterface
from opentuner import Result

log = logging.getLogger("cpython_pyperformance")


# ---------------------------------------------------------------------------
# Tunable GCC -f compile flags (stored here without the leading "f").
# Each flag takes on / off / default:
#   on       -> -f<flag>      (e.g. unroll-loops -> -funroll-loops)
#   off      -> -fno-<flag>   (e.g. unroll-loops -> -fno-unroll-loops)
#   default  -> not specified (leave it to -O3's default behavior)
# Only flags that plausibly affect CPython performance and whose -fno- form is
# valid are listed here, to avoid build failures.
# ---------------------------------------------------------------------------
COMPILE_FLAGS = [
    "unroll-loops",
    "ipa-pta",
    "tree-vectorize",
    "omit-frame-pointer",
    "predictive-commoning",
    "gcse-after-reload",
    "reorder-blocks-and-partition",
    "devirtualize-speculatively",
    "graphite-identity",
    "tracer",
    "tree-loop-distribute-patterns",
    "inline-functions",
]

# GCC --param parameters as (name, min, max). Ranges must match
# `gcc --help=params`, otherwise GCC errors with "not between 0 and N".
GCC_PARAMS = [
    ("early-inlining-insns", 0, 300),
    ("inline-unit-growth", 0, 100),
    ("max-inline-insns-auto", 0, 100),
    ("predictable-branch-outcome", 0, 50),  # gcc 11 valid range is <0,50>
]

# Second wave of dimensions (2026-11-20).  These cover four areas the first
# space missed: code-generation overhead (CET / PLT), LTO partitioning, PGO
# profile use, and BOLT's own sub-options.  Each entry is
# (name, values, tier); tier 1 = expected to matter, tier 2 = worth trying.
# "default" always means "let CPython's configure decide".
NEW_PARAMS = [
    # -- tier 1 ------------------------------------------------------
    # Ubuntu's gcc defaults to -fcf-protection=full, which puts endbr64 on
    # every indirect-branch target -- the computed-goto dispatch is exactly
    # that shape, so disabling CET can pay off on interpreters.
    ("cf-protection", ["default", "none"], 1),
    # CPython 3.12 passes -flto-partition=none itself (3.16 dropped it);
    # "one" merges every LTO partition so cross-module inlining sees the
    # whole program.  Costs a lot of link-time memory.
    ("lto-partition", ["default", "one", "balanced"], 1),
    # Treat functions absent from the PGO training set as cold; compacts
    # the hot path.  Risk: cold code (rarely exercised by benchmarks) slows.
    ("pgo", ["default", "partial-training"], 1),
    ("align-functions", ["default", "16", "32", "64"], 1),
    ("vect-cost-model", ["default", "very-cheap", "dynamic"], 1),
    # -- tier 2 ------------------------------------------------------
    # Replaces CPython's default BOLT_APPLY_FLAGS wholesale; only takes
    # effect with --enable-bolt.
    ("bolt-preset", ["default", "icf-all", "aggressive", "minimal"], 2),
    ("no-plt", ["default", "on"], 2),
    ("ipa-icf", ["default", "on", "off"], 2),
    ("linker", ["default", "lld", "gold"], 2),
]

# BOLT_APPLY_FLAGS replacements.  The "default" entry means "do not export
# BOLT_APPLY_FLAGS at all", i.e. use CPython's own defaults (with the
# -frame-opt=hot workaround applied by _build()).
BOLT_PRESETS = {
    "icf-all": ("-reorder-blocks=ext-tsp -reorder-functions=cdsort "
                "-split-functions -icf=all -inline-all -split-eh "
                "-reorder-functions-use-hot-size -peepholes=none "
                "-jump-tables=aggressive -inline-ap "
                "-indirect-call-promotion=all -use-gnu-stack"),
    "aggressive": ("-reorder-blocks=ext-tsp -reorder-functions=cdsort "
                   "-split-functions -icf=all -inline-all -split-eh "
                   "-reorder-functions-use-hot-size -peepholes=none "
                   "-jump-tables=aggressive -inline-ap "
                   "-indirect-call-promotion=all -dyno-stats -use-gnu-stack"),
    "minimal": "-reorder-blocks=ext-tsp -reorder-functions=cdsort -icf=all",
}

# Interaction tests.  One-factor-at-a-time cannot see these: each side can be
# neutral on its own while the combination moves the needle.  Every entry is
# applied on top of the base configuration.
PAIR_TESTS = [
    # LTO visibility (one partition) only pays off with enough inlining
    # headroom; with the default limits the extra visibility goes unused.
    ("lto-inline-headroom",
     {"lto-partition": "one", "inline-unit-growth": 100,
      "max-inline-insns-auto": 100}),
    ("lto-early-inlining",
     {"lto-partition": "one", "early-inlining-insns": 300}),
    # BOLT reorders code post-link; compiler-side layout flags compete with it.
    ("bolt-vs-compiler-layout",
     {"bolt-preset": "icf-all", "reorder-blocks-and-partition": "off",
      "gcse-after-reload": "off"}),
    ("bolt-aggressive-no-layout",
     {"bolt-preset": "aggressive", "reorder-blocks-and-partition": "off"}),
    # The vectorizer cost model is only observable when vectorization is on.
    ("vectorize-very-cheap",
     {"tree-vectorize": "on", "vect-cost-model": "very-cheap"}),
    ("vectorize-dynamic",
     {"tree-vectorize": "on", "vect-cost-model": "dynamic"}),
]


def _paley_pb_rows(n_factors):
    """Plackett-Burman design rows (lists of +1/-1).

    12 runs for up to 11 two-level factors, 8 runs for up to 7.  Built from a
    Paley Hadamard matrix (order q+1 for prime q == 3 mod 4) and verified:
    every pair of columns must be orthogonal, otherwise the main effects are
    not separable.
    """
    q = 7 if n_factors <= 7 else 11
    residues = {(i * i) % q for i in range(1, q)}

    def chi(a):
        a %= q
        if a == 0:
            return 0
        return 1 if a in residues else -1

    hadamard = [[1] * (q + 1)]
    for i in range(q):
        hadamard.append([1] + [(-1 if i == j else chi(i - j))
                               for j in range(q)])
    # Delete the first column (which is all +1 in a normalised Hadamard
    # matrix) and keep all q+1 rows: the result is the PB design.  The
    # criterion is orthogonality of *columns* -- that is what makes the main
    # effects separately estimable -- so check exactly that.
    rows = [row[1:] for row in hadamard]
    nrows = len(rows)
    for i in range(len(rows[0])):
        for j in range(i + 1, len(rows[0])):
            if sum(r[i] * r[j] for r in rows) != 0:
                raise AssertionError("PB design is not orthogonal")
        if abs(sum(r[i] for r in rows)) > 1e-9:
            raise AssertionError("PB column is not balanced")
    if nrows not in (8, 12):
        raise AssertionError("unexpected PB run count: %d" % nrows)
    return [row[:n_factors] for row in rows]


def _promising_value(name, values, overrides):
    """The value a screening run should test for this factor."""
    if name in overrides:
        return overrides[name]
    candidates = [v for v in values if v != "default"]
    return candidates[-1] if candidates else None


class CpythonTuner(MeasurementInterface):
    def __init__(self, *pargs, **kwargs):
        kwargs.setdefault("program_name", "cpython")
        super(CpythonTuner, self).__init__(*pargs, **kwargs)
        # Build cache keyed by (cflags, ldflags) to avoid rebuilding the same
        # configuration twice.
        self._build_cache = {}

    # ------------------------------------------------------------------
    # Search space
    # ------------------------------------------------------------------
    def manipulator(self):
        manipulator = ConfigurationManipulator()

        # Optimization level. Placed in CFLAGS, after OPT (-O3), so it really
        # overrides the default.
        manipulator.add_parameter(EnumParameter("opt", ["-O2", "-O3"]))
        # Whether to target the local CPU microarchitecture
        # (-march=native / -mtune=native).
        manipulator.add_parameter(EnumParameter("march", ["default", "native"]))
        # BOLT post-link optimization (new in CPython 3.12). A configure-level
        # flag, so it is handled by _cfg_to_configure_flags, not CFLAGS.
        manipulator.add_parameter(EnumParameter("bolt", ["on", "off"]))

        for flag in COMPILE_FLAGS:
            manipulator.add_parameter(
                EnumParameter(flag, ["on", "off", "default"]))

        for param, lo, hi in GCC_PARAMS:
            manipulator.add_parameter(IntegerParameter(param, lo, hi))

        # Second wave of dimensions (see NEW_PARAMS); --space-size controls
        # whether tier 2 is included so a scan run can stay cheap.
        tiers = {1, 2} if self.args.space_size == "full" else {1}
        for name, values, tier in NEW_PARAMS:
            if tier in tiers:
                manipulator.add_parameter(EnumParameter(name, values))

        return manipulator

    # ------------------------------------------------------------------
    # Turn a configuration into CFLAGS / LDFLAGS strings
    # ------------------------------------------------------------------
    def _cfg_to_cflags(self, cfg):
        flags = [cfg["opt"]]
        if cfg["march"] == "native":
            flags += ["-march=native", "-mtune=native"]

        for flag in COMPILE_FLAGS:
            value = cfg[flag]
            if value == "on":
                flags.append("-f" + flag)
            elif value == "off":
                flags.append("-fno-" + flag)

        for param, _lo, _hi in GCC_PARAMS:
            flags.append("--param=%s=%d" % (param, cfg[param]))

        # Second-wave dimensions.  cfg.get() because these keys are absent
        # when the parameter was filtered out by --space-size.
        if cfg.get("cf-protection", "default") == "none":
            flags.append("-fcf-protection=none")
        lto_part = cfg.get("lto-partition", "default")
        if lto_part != "default":
            flags.append("-flto-partition=" + lto_part)
        if cfg.get("pgo", "default") == "partial-training":
            flags.append("-fprofile-partial-training")
        align = cfg.get("align-functions", "default")
        if align != "default":
            flags.append("-falign-functions=" + align)
        vcm = cfg.get("vect-cost-model", "default")
        if vcm != "default":
            flags.append("-fvect-cost-model=" + vcm)
        if cfg.get("no-plt", "default") == "on":
            flags.append("-fno-plt")
        icf = cfg.get("ipa-icf", "default")
        if icf == "on":
            flags.append("-fipa-icf")
        elif icf == "off":
            flags.append("-fno-ipa-icf")

        return " ".join(flags)

    def _cfg_to_ldflags(self, cfg):
        ld = []
        linker = cfg.get("linker", "default")
        if linker != "default":
            ld.append("-fuse-ld=" + linker)
        return " ".join(ld)

    def _cfg_to_bolt_apply_flags(self, cfg):
        """BOLT_APPLY_FLAGS replacement, or None to keep CPython's defaults."""
        preset = cfg.get("bolt-preset", "default")
        if preset == "default" or cfg.get("bolt") != "on":
            return None
        return BOLT_PRESETS[preset]

    def _cfg_to_configure_flags(self, cfg):
        """Return extra configure-level flags driven by the configuration.

        BOLT (--enable-bolt) is a post-link optimizer introduced in CPython
        3.12 and cannot be expressed as a CFLAGS, so it is appended to the
        configure command instead. It requires llvm-bolt and merge-fdata on
        PATH (configure errors out otherwise, which the tuner sees as a build
        failure).
        """
        flags = []
        if cfg["bolt"] == "on":
            flags.append("--enable-bolt")
        return " ".join(flags)

    # ------------------------------------------------------------------
    # Build CPython
    # ------------------------------------------------------------------
    def _build(self, build_dir, cflags, ldflags, extra_configure_flags="",
               bolt_apply_flags=None):
        build_dir = os.path.abspath(build_dir)
        prefix = os.path.join(build_dir, "install")
        configure = os.path.join(self.args.source_dir, "configure")
        logfile = os.path.join(build_dir, "build.log")

        # Fixed configure flags (PGO/LTO, etc.) plus any tunable
        # configure-level flags such as --enable-bolt.
        configure_flags = self.args.configure_flags
        if extra_configure_flags:
            configure_flags = (configure_flags + " " + extra_configure_flags).strip()

        os.makedirs(build_dir, exist_ok=True)

        # llvm-bolt 23 miscompiles the binary when -frame-opt=hot and
        # -indirect-call-promotion=all are both active (both are in
        # cpython's default BOLT_APPLY_FLAGS): the bolt-optimized python
        # segfaults in _PyEval_EvalFrameDefault with zeroed arguments on
        # some builds (bisection 2026-10-27, /tmp/cpython-segv).  Dropping
        # -frame-opt=hot alone avoids it; every other optimization
        # (reorder-blocks/functions, icf, icp, ...) is kept.
        bolt_fix = ""
        if "--enable-bolt" in configure_flags:
            bolt_fix = "sed -i 's/ -frame-opt=hot//' Makefile; "

        # A BOLT preset replaces CPython's BOLT_APPLY_FLAGS wholesale
        # (configure reads it as an AC_ARG_VAR and bakes it into the
        # Makefile), so it has to be exported before configure runs.
        bolt_env = ""
        if bolt_apply_flags:
            bolt_env = "export BOLT_APPLY_FLAGS=%s; " % shlex.quote(bolt_apply_flags)

        # Run cd/configure/make/make install inside a subshell so the whole
        # output is redirected to build.log, making configure/make failures
        # visible in the log.
        cmd = (
            "( set -e; "
            "cd {build_dir}; "
            "export CFLAGS={cflags}; "
            "export LDFLAGS={ldflags}; "
            "{bolt_env}"
            "{configure} --prefix={prefix} {configure_flags}; "
            "{bolt_fix}"
            "make -j{jobs}; "
            "make install ) > {log} 2>&1"
        ).format(
            build_dir=shlex.quote(build_dir),
            cflags=shlex.quote(cflags),
            ldflags=shlex.quote(ldflags),
            configure=shlex.quote(configure),
            prefix=shlex.quote(prefix),
            configure_flags=configure_flags,
            bolt_env=bolt_env,
            bolt_fix=bolt_fix,
            jobs=self.args.jobs,
            log=shlex.quote(logfile),
        )

        log.info("building: CFLAGS=%s LDFLAGS=%s CONFIGURE=%s",
                 cflags, ldflags, configure_flags)
        result = self.call_program(cmd, limit=self.args.build_timeout)

        if result["timeout"]:
            log.error("build timed out: %s", self._tail(logfile))
            return None
        if result["returncode"] != 0:
            log.error("build failed (returncode=%s):\n%s",
                      result["returncode"], self._tail(logfile))
            return None
        return prefix

    def _find_python(self, prefix):
        """Locate the built python3 executable under install/bin."""
        bin_dir = os.path.join(prefix, "bin")
        if not os.path.isdir(bin_dir):
            return None
        candidates = sorted(
            f for f in os.listdir(bin_dir)
            if f.startswith("python3.") and "config" not in f
        )
        if candidates:
            return os.path.join(bin_dir, candidates[0])
        for name in ("python3", "python"):
            path = os.path.join(bin_dir, name)
            if os.path.exists(path):
                return path
        return None

    # ------------------------------------------------------------------
    # Run pyperformance and parse the score
    # ------------------------------------------------------------------
    def _run_pyperformance(self, build_dir, python_bin, result_path, fast=None):
        """Run pyperformance; return "OK" / "TIMEOUT" / "ERROR"."""
        if fast is None:
            fast = self.args.fast
        logfile = os.path.join(build_dir, "pyperformance.log")

        cmd = [
            # Drop SETUPTOOLS_USE_DISTUTILS from the child environment: with
            # "stdlib" setuptools' distutils shim stays inactive and 3.12 has
            # no stdlib distutils, so benchmarks importing distutils
            # (sympy 1.8, django 3.2.4) would die on every run.
            "env", "-u", "SETUPTOOLS_USE_DISTUTILS",
            self.args.pyperformance_python, "-m", "pyperformance", "run",
            "--python", python_bin,
            "-o", result_path,
        ]
        if fast:
            cmd.append("-f")
        if self.args.benchmarks:
            # "=" form so exclusion lists ("-sympy,...") survive argparse.
            cmd += ["-b=" + self.args.benchmarks]

        # pyperformance resolves its venv root relative to the cwd
        # (_venv.get_venv_root -> abspath("venv/...")), so run from a
        # dedicated empty subdir of build_dir: the venv still lands under
        # build_dir for cleanup, but the cwd must NOT be the build root --
        # it contains pybuilddir.txt, and setuptools' distutils shim
        # (_distutils_hack.DistutilsMetaFinder.is_cpython) disables itself
        # when that file exists in the cwd ("am I inside the CPython
        # repo?").  On 3.12 (PEP 632) there is no stdlib distutils to fall
        # back to, so sympy 1.8 and django 3.2.4 (both import distutils at
        # runtime) died on every single run.
        run_cwd = os.path.join(build_dir, "bench")
        os.makedirs(run_cwd, exist_ok=True)
        result = self.call_program(
            cmd, limit=self.args.run_timeout, cwd=run_cwd)

        # Persist stdout/stderr for troubleshooting individual runs.
        with open(logfile, "wb") as fd:
            fd.write(result.get("stdout") or b"")
            fd.write(b"\n")
            fd.write(result.get("stderr") or b"")

        if result["timeout"]:
            log.error("pyperformance timed out: %s", self._tail(logfile))
            return "TIMEOUT"
        if result["returncode"] != 0:
            log.error("pyperformance failed (returncode=%s):\n%s",
                      result["returncode"], self._tail(logfile))
            return "ERROR"
        return "OK"

    def _parse_score(self, result_path):
        """Return the geometric mean of all benchmark medians (seconds)."""
        try:
            import pyperf
        except ImportError:
            log.error("host python is missing pyperf, cannot parse results")
            return None

        try:
            suite = pyperf.BenchmarkSuite.load(result_path)
        except Exception as exc:  # noqa: BLE001
            log.error("cannot parse pyperformance result %s: %s",
                      result_path, exc)
            return None

        times = []
        for bench in suite.get_benchmarks():
            median = bench.median()
            if median and median > 0:
                times.append(median)
        if not times:
            log.error("no valid benchmark data in pyperformance result")
            return None

        return math.exp(sum(math.log(t) for t in times) / len(times))

    # ------------------------------------------------------------------
    # OpenTuner entry point: build + run
    # ------------------------------------------------------------------
    def run(self, desired_result, input, limit):  # noqa: A002
        cfg = desired_result.configuration.data

        got = self._get_build(cfg, "build-%d" % desired_result.id)
        if got is None:
            return Result(state="ERROR", time=float("inf"))
        build_dir, python_bin = got

        result_path = os.path.join(build_dir, "pyperformance.json")
        status = self._run_pyperformance(build_dir, python_bin, result_path)
        self._post_run_cleanup(build_dir)

        if status == "TIMEOUT":
            # A partial result after a timeout only covers the benchmarks
            # that finished (roughly the fast ones first), which would bias
            # the geomean, so do not salvage it.
            return Result(state="TIMEOUT", time=float("inf"))

        score = self._parse_score(result_path)
        if score is None:
            return Result(state="ERROR", time=float("inf"))

        if status == "ERROR":
            log.warning("pyperformance failed; salvaged partial score "
                        "(broken benchmarks excluded)")
        else:
            log.info("score (geomean of medians) = %.4f s", score)
        return Result(time=score)

    # ------------------------------------------------------------------
    # Build cache shared by the search phase and the final top-N phase
    # ------------------------------------------------------------------
    def _get_build(self, cfg, dirname):
        """Return (build_dir, python_bin) for cfg, building it if needed."""
        cflags = self._cfg_to_cflags(cfg)
        ldflags = self._cfg_to_ldflags(cfg)
        configure_flags = self._cfg_to_configure_flags(cfg)
        bolt_flags = self._cfg_to_bolt_apply_flags(cfg)

        cache_key = (cflags, ldflags, configure_flags, bolt_flags)
        cached = self._build_cache.get(cache_key)
        if cached is not None:
            return cached

        build_dir = os.path.join(
            os.path.abspath(self.args.build_root), dirname)
        prefix = self._build(build_dir, cflags, ldflags, configure_flags,
                             bolt_apply_flags=bolt_flags)
        if prefix is None:
            return None

        python_bin = self._find_python(prefix)
        if python_bin is None:
            log.error("could not find a python3 executable under install")
            return None

        self._build_cache[cache_key] = (build_dir, python_bin)
        return (build_dir, python_bin)

    def _post_run_cleanup(self, build_dir):
        """Remove the venv and build intermediates after one measurement."""
        # Remove the venv after the run to save disk (deps are already in the
        # pip cache and would just be reinstalled if the config is re-measured).
        venv_dir = os.path.join(build_dir, "bench", "venv")
        if not self.args.keep_venv and os.path.isdir(venv_dir):
            shutil.rmtree(venv_dir, ignore_errors=True)

        # Delete the out-of-tree build tree right after this run instead of
        # waiting for the whole tuning session to end: the object files and
        # generated sources are large and would otherwise exhaust disk space
        # across many iterations. install/ and the logs are kept so a
        # re-measurement of the same configuration can reuse the cached build.
        if not self.args.keep_builds:
            self._cleanup_build_intermediates(build_dir)

    # ------------------------------------------------------------------
    # Final phase: re-measure the top-N configurations in full mode
    # ------------------------------------------------------------------
    def _top_config_results(self, n):
        """Best n distinct successful configurations, best-first."""
        ranked = []
        seen = set()
        for result in self.driver.results_query(objective_ordered=True):
            if result.state != "OK" or result.time is None:
                continue
            if not math.isfinite(result.time):
                continue
            cfg = result.configuration.data
            key = json.dumps(cfg, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            ranked.append((result.time, cfg))
            if len(ranked) >= n:
                break
        return ranked

    def _remeasure_topn(self, n):
        """Re-measure the top-n configurations in full pyperformance mode.

        Search runs use --fast (one value per benchmark); its noise can
        reorder closely-spaced configurations, so the final ranking is
        redone without -f and the champion is picked from these full-mode
        scores.  Builds are reused from the cache when possible.
        """
        ranked = self._top_config_results(n)
        entries = []
        for rank, (fast_time, cfg) in enumerate(ranked, 1):
            log.info("top-%d/%d full-mode re-measure: CFLAGS=%s",
                     rank, len(ranked), self._cfg_to_cflags(cfg))
            full_time = None
            build_dir = None
            got = self._get_build(cfg, "build-top%d" % rank)
            if got is not None:
                build_dir, python_bin = got
                result_path = os.path.join(
                    build_dir, "pyperformance_full.json")
                status = self._run_pyperformance(
                    build_dir, python_bin, result_path, fast=False)
                self._post_run_cleanup(build_dir)
                if status == "OK":
                    full_time = self._parse_score(result_path)
            if full_time is None:
                log.error("top-%d full-mode re-measure failed", rank)
            else:
                log.info("top-%d full-mode score = %.4f s (fast: %.4f s)",
                         rank, full_time, fast_time)
            entries.append({
                "rank_by_fast": rank,
                "time_fast": fast_time,
                "time_full": full_time,
                "config": cfg,
                "build_dir": build_dir,
            })
        # Full-mode score decides the final order; failed re-measures sink.
        entries.sort(key=lambda e: (e["time_full"] is None,
                                    e["time_full"] or 0.0))
        return entries

    def _write_topn_results(self, entries):
        """Print and save the full-mode ranking of the top configurations."""
        out = os.path.join(self.args.output_dir, "topn_results.json")
        records = []
        print("Top-%d configurations (ranked by FULL-mode score):"
              % len(entries))
        for rank, entry in enumerate(entries, 1):
            cfg = entry["config"]
            configure_flags = (self.args.configure_flags + " " +
                               self._cfg_to_configure_flags(cfg)).strip()
            print("  #%d  full=%s  fast=%.4f s" % (
                rank,
                ("%.4f s" % entry["time_full"]
                 if entry["time_full"] is not None else "FAILED"),
                entry["time_fast"]))
            print("      CFLAGS=%s" % self._cfg_to_cflags(cfg))
            print("      CONFIGURE=%s" % configure_flags)
            records.append({
                "rank": rank,
                "time_fast": entry["time_fast"],
                "time_full": entry["time_full"],
                "cflags": self._cfg_to_cflags(cfg),
                "ldflags": self._cfg_to_ldflags(cfg),
                "configure_flags": configure_flags,
                "config": cfg,
                "build_dir": entry["build_dir"],
                "pyperformance_full_json": (
                    os.path.join(entry["build_dir"],
                                 "pyperformance_full.json")
                    if entry["build_dir"] else None),
            })
        with open(out, "w") as fd:
            json.dump(records, fd, indent=2, sort_keys=True)
        print("  written to:", out)

    # ------------------------------------------------------------------
    # Emit the best configuration at the end of tuning
    # ------------------------------------------------------------------
    def save_final_config(self, configuration):
        cfg = configuration.data

        # Optional final phase: re-rank the best configurations with full
        # (non-fast) pyperformance runs; the champion then comes from the
        # full-mode ranking, not from the noisy --fast search.
        entries = []
        if self.args.fast and self.args.topn > 0:
            entries = self._remeasure_topn(self.args.topn)
            if entries and entries[0]["time_full"] is not None:
                cfg = entries[0]["config"]

        cflags = self._cfg_to_cflags(cfg)
        ldflags = self._cfg_to_ldflags(cfg)
        configure_flags = self._cfg_to_configure_flags(cfg)

        # Fixed configure flags (PGO/LTO, etc.) plus tunable configure-level
        # flags (e.g. --enable-bolt).
        full_configure_flags = self.args.configure_flags
        if configure_flags:
            full_configure_flags = (full_configure_flags + " " + configure_flags).strip()

        os.makedirs(self.args.output_dir, exist_ok=True)
        out_json = os.path.join(self.args.output_dir, "best_config.json")
        out_sh = os.path.join(self.args.output_dir, "best_flags.sh")

        with open(out_json, "w") as fd:
            json.dump(cfg, fd, indent=2, sort_keys=True)

        with open(out_sh, "w") as fd:
            fd.write("#!/bin/sh\n")
            fd.write("# Best CPython compile/link options found by OpenTuner\n")
            fd.write("export CFLAGS=%s\n" % shlex.quote(cflags))
            fd.write("export LDFLAGS=%s\n" % shlex.quote(ldflags))
            # Same llvm-bolt workaround as _build(): strip -frame-opt=hot so
            # reproducing a bolt build does not hit the bolt miscompile.
            bolt_fix = ("sed -i 's/ -frame-opt=hot//' Makefile && "
                        if "--enable-bolt" in full_configure_flags else "")
            fd.write(
                "cd build/best && %s/configure --prefix=$PWD/install %s && "
                "%s"
                "make -j && make install\n"
                % (shlex.quote(self.args.source_dir), full_configure_flags,
                   bolt_fix))

        print("Best configuration written to:")
        print("  ", out_json)
        print("  ", out_sh)
        print("  CFLAGS =", cflags)
        print("  LDFLAGS =", ldflags)
        print("  CONFIGURE =", full_configure_flags)

        if entries:
            self._write_topn_results(entries)

        # Preserve the best configuration's installed interpreter so it can be
        # used directly for the final comparison without a rebuild. The build
        # cache maps (cflags, ldflags, configure flags) to the build dir that
        # produced it.
        cached = self._build_cache.get((cflags, ldflags, configure_flags))
        keep = ()
        if cached is not None:
            keep = (os.path.basename(cached[0]),)
            print("  tuned python:", cached[1])

        # Delete the intermediate build directories now that tuning is done,
        # keeping the best one.
        if not self.args.keep_builds:
            self._cleanup_build_dirs(keep=keep)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _cleanup_build_intermediates(self, build_dir):
        """Delete the out-of-tree build tree, keeping install/ and the logs.

        After ``make install`` the interpreter under install/ is self-contained,
        so the object files and generated sources in build_dir are no longer
        needed; keeping install/ lets a re-measurement reuse the cached build.
        """
        keep = ("install", "bench", "build.log", "pyperformance.log",
                "pyperformance.json", "pyperformance_full.json")
        if not os.path.isdir(build_dir):
            return
        for name in os.listdir(build_dir):
            if name in keep:
                continue
            path = os.path.join(build_dir, name)
            if os.path.islink(path) or os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)

    def _cleanup_build_dirs(self, keep=()):
        """Remove all build-<id>/build-top<N> dirs under --build-root, except `keep`."""
        build_root = os.path.abspath(self.args.build_root)
        if not os.path.isdir(build_root):
            return
        for name in os.listdir(build_root):
            if re.fullmatch(r"build-(\d+|top\d+)", name) and name not in keep:
                shutil.rmtree(os.path.join(build_root, name), ignore_errors=True)
                log.info("removed intermediate build directory %s", name)

    @staticmethod
    def _tail(path, n=40):
        try:
            with open(path, "rb") as fd:
                lines = fd.readlines()
            return b"".join(lines[-n:]).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return ""


def _add_args(argparser):
    argparser.add_argument(
        "--source-dir", default=os.path.expanduser("~/gerrit/cpython"),
        help="CPython source directory (containing configure)")
    argparser.add_argument(
        "--build-root", default="./builds",
        help="build directory, one build-<id> subdir per configuration")
    argparser.add_argument(
        "--pyperformance-python", default="python3",
        help="host python used to run pyperformance (must have it installed)")
    argparser.add_argument(
        "--configure-flags", default="--enable-optimizations --with-lto",
        help="fixed configure flags (PGO/LTO, etc.)")
    argparser.add_argument(
        "--jobs", type=int, default=os.cpu_count(),
        help="make -j parallelism")
    argparser.add_argument(
        "--benchmarks", default=None,
        help="comma-separated benchmark list passed to pyperformance -b "
             "(default: all)")
    argparser.add_argument(
        "--fast", action="store_true",
        help="pyperformance fast mode, shorten each sample")
    argparser.add_argument(
        "--build-timeout", type=float, default=3600.0,
        help="timeout for a single build (seconds)")
    argparser.add_argument(
        "--run-timeout", type=float, default=7200.0,
        help="timeout for a single pyperformance run (seconds)")
    argparser.add_argument(
        "--keep-venv", action="store_true",
        help="keep the pyperformance venv after each run (removed by default)")
    argparser.add_argument(
        "--output-dir", default=".",
        help="directory for the best-configuration output")
    argparser.add_argument(
        "--keep-builds", action="store_true",
        help="keep intermediate build directories after tuning completes "
             "(removed by default)")
    argparser.add_argument(
        # Default 10 rather than 5: fast-mode repeatability is good (median
        # relative spread 0.17% over 11 repeated measurements of the same
        # configuration) but rare outliers are not -- one fast score was 7%
        # better than its full-mode score. An outlier occupies a re-measure
        # slot and can push the true winner out of the list; five extra
        # full-mode re-measures cost ~2.5 h against a ~50 h search.
        "--topn", type=int, default=10,
        help="with --fast: re-measure the N best configurations in full "
             "pyperformance mode at the end, rank by those scores and write "
             "topn_results.json (0 disables)")
    argparser.add_argument(
        "--space-size", choices=["core", "tier1", "full"], default="full",
        help="core = original 18 dimensions, tier1 = core + the five "
             "high-confidence additions, full = tier1 + tier2 (default)")
    argparser.add_argument(
        "--facet-scan", choices=["off", "tier1", "tier2", "all"],
        default="off",
        help="one-factor-at-a-time scan of the new dimensions around "
             "--scan-base; the generated configurations are injected as "
             "seeds and --test-limit is set to their count")
    argparser.add_argument(
        "--scan-base", default=None,
        help="base configuration (JSON) the facet scan varies; required "
             "with --facet-scan")
    argparser.add_argument(
        "--scan-extra", type=int, default=0,
        help="with --facet-scan: number of random configurations to run "
             "after the scan (default 0, i.e. scan only)")
    argparser.add_argument(
        "--facet-design", choices=["ofat", "pb", "pair", "all"],
        default="ofat",
        help="what the scan generates: ofat = one factor at a time (default), "
             "pb = Plackett-Burman screening (all main effects in 8-12 runs, "
             "interactions show up in the residual), pair = targeted A+B "
             "tests for interactions OFAT cannot see, all = every design")
    argparser.add_argument(
        "--scan-promising", default=None,
        help="per-dimension override for the value the PB design should test, "
             "as name=value[,name=value] (default: the last non-default value)")
    return argparser


def _facet_scan_seeds(args):
    """Write the screening configurations around args.scan_base.

    --facet-design selects what is generated:

    * ``ofat``  one factor at a time -- main effect of every dimension value,
      and the table you look at to decide what deserves a long search;
    * ``pb``    Plackett-Burman design over the selected dimensions -- all
      main effects from 8-12 runs, and a residual that tells you whether
      interactions exist at all;
    * ``pair``  targeted A+B tests for the interactions OFAT structurally
      cannot see (A alone neutral, B alone neutral, A+B large);
    * ``all``   ofat + pb + pair.

    Identical configurations are generated only once (the PB row with every
    factor at "default" is the base itself, for example).
    """
    if not args.scan_base:
        raise SystemExit(
            "--facet-scan/--facet-design require --scan-base <config.json>")
    with open(args.scan_base, encoding="utf-8") as f:
        base = json.load(f)

    # Every configuration handed to OpenTuner must carry a value for every
    # parameter in the search space, otherwise ConfigurationManipulator
    # raises KeyError when it hashes the seed.  Fill the ones the base
    # predates with "default" (= let configure decide).
    for name, _values, _tier in NEW_PARAMS:
        base.setdefault(name, "default")

    tiers = {"tier1": {1}, "tier2": {2}, "all": {1, 2}}[args.facet_scan]
    outdir = os.path.join(args.output_dir, "facet-scan")
    os.makedirs(outdir, exist_ok=True)

    # Optional per-dimension override for what "the promising value" means,
    # e.g. --scan-promising lto-partition=balanced
    overrides = {}
    for item in (args.scan_promising or "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            overrides[key.strip()] = value.strip()

    design = args.facet_design
    wanted = {"ofat", "pb", "pair"} if design == "all" else {design}

    configs = []
    seen = set()

    def add(name, cfg):
        key = json.dumps(cfg, sort_keys=True)
        if key in seen:
            return
        seen.add(key)
        configs.append((name, cfg))

    # The base itself is the control: every other row is compared against it.
    add("base", base)

    if "ofat" in wanted:
        for name, values, tier in NEW_PARAMS:
            if tier not in tiers:
                continue
            for value in values:
                # "default" means "leave it to configure", which is exactly
                # the base -- measuring it again would waste an hour.
                if value == "default":
                    continue
                cfg = dict(base)
                cfg[name] = value
                add("%s=%s" % (name, value), cfg)

    if "pb" in wanted:
        factors = [(name, values) for name, values, tier in NEW_PARAMS
                   if tier in tiers
                   and _promising_value(name, values, overrides) is not None]
        if factors:
            for idx, row in enumerate(_paley_pb_rows(len(factors)), 1):
                cfg = dict(base)
                for (name, values), sign in zip(factors, row):
                    if sign > 0:
                        cfg[name] = _promising_value(name, values, overrides)
                add("pb-%02d" % idx, cfg)

    if "pair" in wanted:
        for name, changes in PAIR_TESTS:
            cfg = dict(base)
            cfg.update(changes)
            add("pair-%s" % name, cfg)

    paths = []
    for name, cfg in configs:
        path = os.path.join(outdir, name.replace("/", "_") + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, sort_keys=True)
        paths.append(path)
    log.info("facet design %s: %d configurations -> %s",
             design, len(paths), outdir)
    return paths


if __name__ == "__main__":
    opentuner.init_logging()
    argparser = opentuner.default_argparser()
    argparser = _add_args(argparser)
    _args = argparser.parse_args()
    if _args.facet_scan != "off":
        _seeds = _facet_scan_seeds(_args)
        _args.seed_configuration = list(_args.seed_configuration) + _seeds
        _args.test_limit = len(_args.seed_configuration) + _args.scan_extra
        log.info("facet scan mode: test-limit=%s", _args.test_limit)
    CpythonTuner.main(_args)
