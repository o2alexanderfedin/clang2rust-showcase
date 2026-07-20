# CRUST-bench results

Scoring methodology: [`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md).
Harness: [`benchmarks/run_crust_bench.sh`](benchmarks/run_crust_bench.sh).

- **Run date:** 2026-07-20
- **Dataset:** [CRUST-bench](https://github.com/anirudhkhatry/CRUST-bench)
  ([paper: arXiv 2504.15254](https://arxiv.org/abs/2504.15254)) — 100 real-world
  C repositories, each paired with a hand-written safe-Rust interface and a
  test suite.
- **Coverage:** all 100 projects scored; 81 of 100 could actually be attempted
  in this run environment (see the breakdown below — the other 19 have
  project-side build defects that prevented deriving a compilation database,
  so the converter never ran on them; they are disclosed, not counted as
  conversion failures).

## Aggregate

| Metric | Result |
|---|---|
| Projects in dataset | 100 |
| Projects the converter could attempt | 81 / 100 |
| **Tier 1 — whole project converts AND every emitted crate compiles** | **18 / 100** (18 of 81 attempted) |
| Emitted crates that compile (across all attempted projects) | 117 / 233 (50%) |
| Tier 2 — CRUST-bench pass@1 (against the hand-written interface) | 0 / 100 (not attempted) |

**Tier-1 passing projects (18):** amp, bostree, btree-map, chtrie, csyncmers,
fft, fs_c, hamta, hydra, kd3, leftpad, lib2bit, libbeaufort, libfor,
murmurhash_c, quadtree, Simple-Sparsehash, vec.

## Per-project breakdown (all 100 accounted for)

| Class | Projects | Meaning |
|---|---|---|
| Tier-1 pass | 18 | Whole project converted; every emitted crate compiles as a Rust library. |
| Converted, some crates don't compile yet | 29 | Whole project converted (94 crates emitted, 38 compile); the rest fail Rust compilation. |
| Partially converted | 18 | Some source files hit unsupported constructs and are declined loudly (never silently mis-translated); 103 crates emitted, 43 compile. |
| Not converted | 16 | Unsupported constructs in every file; the converter declines loudly rather than emit wrong code. |
| Environment-blocked | 19 | The project's own build is defective in this environment, so no compilation database could be derived and the converter never ran. |

Per-project rows: `results/<project>.tsv` in the run's cache directory
(regenerate with the harness — result files are not committed to this repo).

## Tier 2 — pass@1: 0 / 100 (not attempted)

Tier 2 is the benchmark's headline metric: does the emitted Rust compile
against the project's *separately authored* Rust interface and pass
`cargo test`? Reconciling output against each project's third-party,
hand-written interface is out of the product's current focus, so every project
is recorded `not-attempted` — honestly, rather than as a blended failure. For
scale: the benchmark paper's best single-shot model result solved 15 of 100 on
that (stricter) metric; our Tier-1 is a weaker bar and the two numbers are not
directly comparable.

## Framing

clang2rust is tuned for large, self-contained C codebases such as
[SQLite](https://www.sqlite.org/) — where the complete command-line shell,
transpiled to Rust, runs byte-identical to the native build (see the
[README](README.md)). CRUST-bench is a deliberately different target: 100
unrelated third-party repositories with their own build systems and externally
supplied Rust interfaces. On a first honest run, the converter fully converts
47 of the 81 reachable projects (18 of them to fully-compiling Rust) and
declines loudly — never silently mis-translating — where it hits constructs it
does not yet support. We publish these numbers as a transparent baseline to
track over time, not as a figure to inflate or omit.

## Run environment notes

- On macOS, the harness splices the host SDK path into each project's
  compilation database so system headers resolve for a stand-alone parser
  (an environment fix, not a scoring change).
- Makefile-only projects need [`bear`](https://github.com/rizsotto/Bear) to
  record a compilation database; with `bear` installed, most of the 78
  Makefile-only projects became reachable. The 19 still-unreachable projects
  fail inside their own build files (broken make rules, CMake configs
  referencing missing files, or no build system at all).
- The Tier-1 compile check invokes `rustc` directly on each emitted crate
  (`--crate-type=lib --emit=obj`) — the emitted crates are C-ABI translation
  units, so a binary-target build would ask for an entry point that is not
  supposed to exist.

See [`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md) for the full
methodology and `benchmarks/run_crust_bench.sh --help` for harness usage.
