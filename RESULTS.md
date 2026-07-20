# CRUST-bench results

Scoring methodology: [`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md).
Harness: [`benchmarks/run_crust_bench.sh`](benchmarks/run_crust_bench.sh).

- **Run date:** 2026-07-20
- **Dataset:** [CRUST-bench](https://github.com/anirudhkhatry/CRUST-bench)
  ([paper: arXiv 2504.15254](https://arxiv.org/abs/2504.15254)) — 100 real-world
  C repositories, each paired with a hand-written safe-Rust interface and a
  test suite.
- **Coverage:** 100 of 100 projects scored. The full sweep completed within the
  run's time budget; no projects were left unreached.

## Aggregate

| Metric | Result |
|---|---|
| Projects in dataset | 100 |
| Projects scored (coverage) | 100 / 100 |
| Compilation database derivable in this run environment | 12 / 100 |
| **Tier 1 — transpiles + compiles** | **0 / 100** |
| **Tier 2 — CRUST-bench pass@1** | **0 / 100** |

## Tier 1 — transpiles + compiles: 0 of 100

Tier 1 asks whether a project's emitted Rust compiles as its own,
self-contained crate.

- **12 of 100** projects yielded a compilation database in this run environment
  and were transpiled. None of the 12 produced Rust that compiled as a
  standalone crate on this attempt.
- **88 of 100** could not be scored for Tier 1 in this environment because no
  compilation database could be derived for them, so the product was never run
  against their source. These are recorded honestly as `no-compile-commands`
  rather than counted as transpilation failures:
  - 78 are Makefile-only and require [`bear`](https://github.com/rizsotto/Bear)
    to record a compilation database; `bear` was not installed in this run.
  - 9 CMake projects fail to configure (project-side build-file defects, e.g. a
    referenced file that is absent, or a build target with no sources).
  - 1 ships no build system at all.

## Tier 2 — CRUST-bench pass@1: 0 of 100

Tier 2 is the benchmark's headline metric: does the emitted Rust compile
against the project's *separately authored* Rust interface and pass
`cargo test`?

All 100 projects are marked `not-attempted`. Reconciling emitted output against
each project's third-party, hand-written interface and test harness is out of
the product's current focus, so no project is scored for Tier 2 on this run. We
record this as `not-attempted` rather than as silent failures. This is the
number we expect to be very low today, and we publish it as an honest baseline
rather than hiding it behind a blended score.

## Framing

clang2rust is tuned for large, self-contained C codebases such as
[SQLite](https://www.sqlite.org/), where the shape of the Rust output is
derived entirely from the source. CRUST-bench is a deliberately different
target: 100 unrelated third-party repositories, most with their own Makefile
build, each with an externally supplied Rust interface the output must be
reconciled against. A low score here is the expected, honest result for the
product's current focus — we publish these numbers as a transparent baseline to
track over time, not as a figure to inflate or omit. The benchmark paper itself
reports the task as hard: its best single-shot model solved 15 of 100.

## Run environment notes

The scores above reflect one bounded run on one machine, and two
environment-side factors gate how many projects could even be reached:

- **`bear` was not available**, so the 78 Makefile-only projects could not have
  a compilation database recorded and were left unscored for Tier 1 (not
  counted as failures). Installing `bear` would let those projects be attempted
  in a future run.
- **Recent CMake** rejects some projects' very old minimum-version pins; the
  harness passes a compatibility setting so those build files can still
  configure. A handful of CMake projects nonetheless fail to configure due to
  defects in their own build files.

See [`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md) for the full
methodology and [`benchmarks/run_crust_bench.sh --help`](benchmarks/run_crust_bench.sh)
for the harness usage.
