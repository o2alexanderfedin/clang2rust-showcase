# CRUST-bench methodology

This document describes the [CRUST-bench](https://github.com/anirudhkhatry/CRUST-bench)
benchmark, how clang2rust is scored against it, and the operational
constraints of running it locally. It is not a description of clang2rust's
internals — only of the benchmark and the scoring procedure.

## What CRUST-bench is

CRUST-bench ([paper](https://arxiv.org/abs/2504.15254), Khatry et al., 2025)
is a dataset of 100 real-world C repositories, each collected from GitHub
across domains such as system utilities, algorithms, data structures,
networking, and cryptography. Every repository is paired with:

- a hand-written, idiomatic, memory-safe **Rust interface** (`RBench/<project>/interfaces/*.rs`)
  that specifies the public shape the transpiled crate must expose, and
- a **test suite** (`RBench/<project>/bin/*.rs`) written against that
  interface, used to check functional correctness of a transpilation.

The dataset ships as two folders:

```
CBench/<project>/            # original C sources, Makefile or CMake build
RBench/<project>/interfaces/ # hand-written safe-Rust interface (*.rs)
RBench/<project>/bin/        # tests written against that interface (*.rs)
```

Build systems across the 100 projects are a mix of `Makefile` and `CMake`;
neither is uniform, so deriving a compilation database is a per-project step
(see "Operational blockers" below).

## The pass@1 metric

CRUST-bench's headline metric is **pass@1**: for a single transpilation
attempt, does the result (a) compile against the project's hand-written Rust
interface, and (b) pass every test in that project's `bin/` test suite? A
project only counts as solved if both hold on the first attempt — there is
no retry credit.

The benchmark paper reports this as a hard problem: the best model they
evaluated (OpenAI o1, single-shot) solved 15 of 100 projects.

## Our two-tier scoring

clang2rust's benchmark harness (`run_crust_bench.sh`) reports two tiers per
project, rather than collapsing straight to pass@1:

| Tier | Question | What it measures |
|---|---|---|
| 1 — Transpiles | Does the emitted Rust compile as its own, self-contained crate? | Whether clang2rust can process the project's C source at all |
| 2 — CRUST-bench pass@1 | Does the emitted Rust compile against CRUST-bench's hand-written interface, and does `cargo test` pass? | The benchmark's actual headline metric |

Tier 1 is intentionally decoupled from Tier 2: clang2rust does not attempt
to reshape its output to match an externally supplied interface signature
during Tier-1 scoring, so a Tier-1 pass does not imply a Tier-2 pass. Where
a project cannot reach Tier-2 scoring at all (its emitted crate has no
principled way to be spliced against the supplied interface without manual
reconciliation), the harness marks that project `not-attempted` rather than
silently counting it as a failure or omitting it — see `RESULTS.md`.

**Why we expect Tier-2 pass@1 to start low:** clang2rust is currently tuned
against large, self-contained C codebases such as SQLite, where the
transpiled crate's shape is derived entirely from the source. CRUST-bench's
Tier-2 scoring additionally requires reconciling that output against a
*third party's* hand-written interface and test harness per project — a
different problem clang2rust does not yet solve. We publish both tiers so
the gap is visible rather than hidden behind a single blended number.

## Operational blockers

- **`bear` is required for Makefile-only projects.** clang2rust's front end
  needs a `compile_commands.json` compilation database. CMake projects
  produce one directly; Makefile-only projects need
  [`bear`](https://github.com/rizsotto/Bear) to wrap the build and record
  one. Install it (`brew install bear` / `apt install bear`) before running
  the harness against Makefile-only CRUST-bench projects.
- **The dataset is GPL-3.0 and lives in an external cache only.** CRUST-bench
  is distributed under the GNU GPL. To keep this repository's own license
  terms clean, the dataset is never fetched into or committed to this repo —
  `run_crust_bench.sh` downloads it into an external, git-ignored cache
  directory (`--cache`, default outside the repo tree) and reads it from
  there.

## Reproducing

```console
$ benchmarks/run_crust_bench.sh --transpiler ../cpp-to-rust/cpp/build/bin/cpp2rust --cache ~/.cache/crust-bench
```

Add `--dry-run` to see the planned steps (fetch, per-project Tier-1/Tier-2
scoring, aggregate) without executing them. Full flag reference:
`run_crust_bench.sh --help`.
