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

For each configuration the tuner:
  1. builds a python3.10 out-of-tree via configure + make + make install;
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
* per-configuration build/run timeouts are controlled by ``--build-timeout`` /
  ``--run-timeout`` (this fork's ``--test-limit`` is no longer a per-test
  timeout, see above);
* re-running after an interrupt resumes automatically (results are stored in
  opentuner.db);
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

        for flag in COMPILE_FLAGS:
            manipulator.add_parameter(
                EnumParameter(flag, ["on", "off", "default"]))

        for param, lo, hi in GCC_PARAMS:
            manipulator.add_parameter(IntegerParameter(param, lo, hi))

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

        return " ".join(flags)

    def _cfg_to_ldflags(self, cfg):
        # No extra link-stage options for now; extend here if needed
        # (e.g. -Wl,-O1).
        return ""

    # ------------------------------------------------------------------
    # Build CPython
    # ------------------------------------------------------------------
    def _build(self, build_dir, cflags, ldflags):
        build_dir = os.path.abspath(build_dir)
        prefix = os.path.join(build_dir, "install")
        configure = os.path.join(self.args.source_dir, "configure")
        logfile = os.path.join(build_dir, "build.log")

        os.makedirs(build_dir, exist_ok=True)

        # Run cd/configure/make/make install inside a subshell so the whole
        # output is redirected to build.log, making configure/make failures
        # visible in the log.
        cmd = (
            "( set -e; "
            "cd {build_dir}; "
            "export CFLAGS={cflags}; "
            "export LDFLAGS={ldflags}; "
            "{configure} --prefix={prefix} {configure_flags}; "
            "make -j{jobs}; "
            "make install ) > {log} 2>&1"
        ).format(
            build_dir=shlex.quote(build_dir),
            cflags=shlex.quote(cflags),
            ldflags=shlex.quote(ldflags),
            configure=shlex.quote(configure),
            prefix=shlex.quote(prefix),
            configure_flags=self.args.configure_flags,
            jobs=self.args.jobs,
            log=shlex.quote(logfile),
        )

        log.info("building: CFLAGS=%s LDFLAGS=%s", cflags, ldflags)
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
    def _run_pyperformance(self, build_dir, python_bin, result_path):
        """Run pyperformance; return "OK" / "TIMEOUT" / "ERROR"."""
        logfile = os.path.join(build_dir, "pyperformance.log")

        cmd = [
            self.args.pyperformance_python, "-m", "pyperformance", "run",
            "--python", python_bin,
            "-o", result_path,
        ]
        if self.args.fast:
            cmd.append("-f")
        if self.args.benchmarks:
            cmd += ["-b", self.args.benchmarks]

        # Run inside build_dir so pyperformance's venv/ lands under build_dir
        # and can be cleaned up together with it.
        result = self.call_program(
            cmd, limit=self.args.run_timeout, cwd=build_dir)

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
        cflags = self._cfg_to_cflags(cfg)
        ldflags = self._cfg_to_ldflags(cfg)

        cache_key = (cflags, ldflags)
        cached = self._build_cache.get(cache_key)
        if cached is not None:
            build_dir, python_bin = cached
        else:
            build_dir = os.path.join(
                os.path.abspath(self.args.build_root),
                "build-%d" % desired_result.id)
            prefix = self._build(build_dir, cflags, ldflags)
            if prefix is None:
                return Result(state="ERROR", time=float("inf"))

            python_bin = self._find_python(prefix)
            if python_bin is None:
                log.error("could not find a python3 executable under install")
                return Result(state="ERROR", time=float("inf"))
            self._build_cache[cache_key] = (build_dir, python_bin)

        result_path = os.path.join(build_dir, "pyperformance.json")
        status = self._run_pyperformance(build_dir, python_bin, result_path)

        # Remove the venv after the run to save disk (deps are already in the
        # pip cache and would just be reinstalled if the config is re-measured).
        venv_dir = os.path.join(build_dir, "venv")
        if not self.args.keep_venv and os.path.isdir(venv_dir):
            shutil.rmtree(venv_dir, ignore_errors=True)

        # Delete the out-of-tree build tree right after this run instead of
        # waiting for the whole tuning session to end: the object files and
        # generated sources are large and would otherwise exhaust disk space
        # across many iterations. install/ and the logs are kept so a
        # re-measurement of the same configuration can reuse the cached build.
        if not self.args.keep_builds:
            self._cleanup_build_intermediates(build_dir)

        if status != "OK":
            return Result(state=status, time=float("inf"))

        score = self._parse_score(result_path)
        if score is None:
            return Result(state="ERROR", time=float("inf"))

        log.info("score (geomean of medians) = %.4f s", score)
        return Result(time=score)

    # ------------------------------------------------------------------
    # Emit the best configuration at the end of tuning
    # ------------------------------------------------------------------
    def save_final_config(self, configuration):
        cfg = configuration.data
        cflags = self._cfg_to_cflags(cfg)
        ldflags = self._cfg_to_ldflags(cfg)

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
            fd.write(
                "cd build/best && %s/configure --prefix=$PWD/install %s && "
                "make -j && make install\n"
                % (shlex.quote(self.args.source_dir),
                   self.args.configure_flags))

        print("Best configuration written to:")
        print("  ", out_json)
        print("  ", out_sh)
        print("  CFLAGS =", cflags)
        print("  LDFLAGS =", ldflags)

        # Preserve the best configuration's installed interpreter so it can be
        # used directly for the final comparison without a rebuild. The build
        # cache maps (cflags, ldflags) to the build dir that produced it.
        cached = self._build_cache.get((cflags, ldflags))
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
        keep = ("install", "build.log", "pyperformance.log", "pyperformance.json")
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
        """Remove all build-<id> directories under --build-root, except `keep`."""
        build_root = os.path.abspath(self.args.build_root)
        if not os.path.isdir(build_root):
            return
        for name in os.listdir(build_root):
            if re.fullmatch(r"build-\d+", name) and name not in keep:
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
    return argparser


if __name__ == "__main__":
    opentuner.init_logging()
    argparser = opentuner.default_argparser()
    argparser = _add_args(argparser)
    CpythonTuner.main(argparser.parse_args())
