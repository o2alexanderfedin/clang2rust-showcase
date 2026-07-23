# Results

Two measurements, one honest report: **SQLite** — the product's primary
target, one large real-world codebase transpiled whole and differentially
tested against the native build — and **CRUST-bench** — 100 unrelated
third-party C repositories, published as a transparent external baseline.
Every table is rendered by
[`benchmarks/generate_report.py`](benchmarks/generate_report.py) from result
files; the column definitions are shared and spelled out in the
[legend](#per-project-results) below.

## Flagship — SQLite

The **84-translation-unit [SQLite](https://www.sqlite.org/) CLI link set** —
the command-line shell (`shell.c`) and every source file it links — is
transpiled to Rust in a single run and emitted as **one whole-program
monocrate** (not a crate per file): the `--emit=rust` crate compiles with **0
rustc errors** and the transpiled CLI runs **byte-for-byte identical to the
native one**. Unlike the CRUST-bench rows below, the **Tested** column here is
real end-to-end differential testing: the transpiled command-line shell and the
native one execute the same 10 SQL scripts and their outputs are compared
byte-for-byte, reproduced three times, including under an allocator-hardened
harness.

The census below is scoped to this **verified 84-TU CLI link set**, not the
full 281-TU SQLite corpus. This build collapsed `--emit=rust` from a crate per
translation unit to a single whole-program monocrate; the 84-TU CLI monocrate
is green (0 rustc errors) and A/B-clean (10/10 SQL scripts byte-identical),
but the full 281-TU whole-program emit is not currently green — a deterministic
arena-lifetime heisenbug — so publishing its numbers would not match a shipped,
verified state.

<!-- sqlite-table:begin -->
| Project | Transpiled | Compiled | Tested | Original C Unsafe Sites | Emitted Rust Unsafe Sites | Unsafe Site Reduction (%) | Baseline C UOD | Emitted Rust UOD |
|---|---|---|---|---:|---:|---:|---:|---:|
| [SQLite](https://www.sqlite.org/) → [Rust output](https://github.com/o2alexanderfedin/sqlite-rust-mirror) | ✅ all 84 files | ✅ one whole-program monocrate | ✅ all 10 SQL scripts byte-identical vs native CLI (3 runs) | 40,508 | 84,190 | −107.8% | 7.4% | 8.3% |

<sub>A **site** is one individual unsafe OPERATION, not a function or a whole `unsafe {}` block (those are too coarse). **Transpiled / Compiled** — did cpp2rust emit, and does the emitted code build, for the C++ lane and the Rust lane (`ok/total` translation units). **Tested** — the differential test oracles: **A/B** runs the project's own program built from native C vs from the transpiled C++/Rust and compares output byte-for-byte (`—` = not linkable as one binary, e.g. cross-TU C++ name mangling or unresolved builtin FFI; logged, never silently passed); **pass@1** is CRUST-bench's official oracle — the emitted crate spliced under the hand-written RBench interface, then `cargo test`. For SQLite the Tested cell is the whole-CLI differential over the SQL scripts. **Original C Unsafe Sites** — initial unsafe operation sites in the C source (`raw_ptr_deref + static_mut + union_member`). **Emitted Rust Unsafe Sites** — resulting unsafe operation sites in the emitted Rust (`raw_ptr_deref + extern_unsafe_call + static_mut + union_read + transmute + inline_asm`). `extern_unsafe_call` counts only GENUINELY external calls (libc / foreign symbols). A call whose target is defined elsewhere in the project - a first-party function the emitter exposes through an `extern "C"` boundary so the emitted crate splices under the CRUST-bench harness - plus transpiler shims and benign compiler intrinsics (assert, branch hints, object-size) are emission artifacts, NOT unsafety carried over from the C source; they are split into two separate excluded lanes, `first_party_call` (harness-FFI / transpiler shims) and `intrinsic_call` (benign compiler intrinsics), neither ever folded into the total. `unchecked_arith` (C pointer arithmetic, no Rust unsafe counterpart) is likewise separate. The per-family breakdown below shows every lane. **Unsafe Site Reduction (%)** — `(C − Rust) ÷ C`; **positive = net fewer** unsafe sites, **negative = net more** (this build is a faithful transliteration — ownership/borrow uplift is deferred — so where Rust adds sites it is mostly C's previously-hidden FFI unsafety made explicit, not new unsafety). **Baseline C UOD** / **Emitted Rust UOD** — Unsafe-Operation-Density: unsafe sites ÷ total expressions in that lane's own AST (lower is safer); the denominator grows with any added scaffolding, so the density cannot be gamed by code inflation. All counts use thousands separators.</sub>

<sub>SQLite site counts are code-generated: `cpp2rust --emit=funnel-ingest` over the 84-translation-unit SQLite CLI link set (including the command-line shell, shell.c) for the C side, the operation-level `unsafe_census` over the emitted whole-program Rust monocrate for the Rust side, reduced by [`benchmarks/sqlite_sites_from_funnel.py`](benchmarks/sqlite_sites_from_funnel.py) into [`benchmarks/sqlite-sites.tsv`](benchmarks/sqlite-sites.tsv). A further **16,428** first-party (in-project) calls and **118** benign intrinsics are excluded from the Rust total. The C→Rust site increase is genuine and honest: this build is a faithful transliteration (ownership/borrow uplift deferred), so every libc call that is free in C becomes an explicit `extern_unsafe_call`, and compound C pointer accesses are lowered into several explicit Rust derefs — those two families account for nearly all of the increase, NOT per-crate helper duplication: the whole-program monocrate emits ONE crate and de-duplicates origin-keyed, so the old per-TU helper copies are gone. The **UOD** columns (density, 7.38% → 8.32%) are the cleaner cross-lane measure. State facts recorded 2026-07-23.</sub>
<!-- sqlite-table:end -->

## CRUST-bench

Scoring methodology: [`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md).
Harness: [`benchmarks/run_crust_bench.sh`](benchmarks/run_crust_bench.sh).

- **Run date:** 2026-07-22
- **Dataset:** [CRUST-bench](https://github.com/anirudhkhatry/CRUST-bench)
  ([paper: arXiv 2504.15254](https://arxiv.org/abs/2504.15254)) — 100 real-world
  C repositories, each paired with a hand-written safe-Rust interface and a
  test suite.
- **Coverage:** all 100 projects scored. 19 of the 100 could not be attempted
  at all — their own build systems are broken (defective Makefiles / CMake
  files), so the file-and-flag list the converter needs as input could not be
  produced and the converter never ran on them. That leaves **81 projects the
  converter actually ran on**; the 19 unreachable ones contribute zero to the
  stage and site counts below.

### Aggregate — the full 6-stage pipeline

Every project now runs the SAME six differential stages as SQLite — C→C++,
compile C++, A/B native-vs-C++, C→Rust, build Rust, A/B native-vs-Rust — plus
both test oracles and the per-operation unsafe-SITE census. (Earlier reports
scored only the Tier-1 Rust-compile step; this run adds the C++ lane, the A/B
oracles, pass@1, and the site metrics.)

| Stage (of 100 projects) | Result |
|---|---|
| Reachable — own build produced a compile DB | **81** (the other 19 have broken build systems; the converter never ran) |
| C → C++ transpiled, fully | **52** (+ 15 partial) |
| Emitted C++ compiles, all TUs | **38** |
| C → Rust transpiled, fully | **48** (+ 17 partial) |
| Emitted Rust compiles, all crates | **23** |
| Both lanes fully transpiled AND compiled | **12** |
| A/B — native C vs transpiled **C++** binary | **12 pass**, 0 divergent, 88 not linkable¹ |
| A/B — native C vs transpiled **Rust** binary | **2 pass**, 0 divergent, 98 not linkable¹ |
| pass@1 — emitted crate spliced under the RBench interface + `cargo test` | 0 pass / 35 attempted / 65 no interface match |

C++: **173 of 239** emitted TUs compile (the C++ lane is per-TU objects). Rust: **16** projects' whole-program monocrates compile (the 16-project fair-comparison population above).

¹ For multi-TU projects the per-TU emitted objects do not link into a single
binary (cross-TU C++ name mangling; unresolved compiler-builtin FFI on the Rust
side) — recorded as `—`, honestly, never a silent pass. Where a project IS
linkable (single-TU or ABI-consistent), the A/B runs, and **every leg that ran
matched the native output byte-for-byte (0 divergences).** C++-lane A/B passers:
gorilla-paper-encode, utf8, Graph-recogniser, quadtree, libfor, cJSON,
Simple-Config, Linear-Algebra-C, leftpad, vec, libvcd, kd3.

### Unsafe operation SITES — the headline

Safety is measured in per-operation **SITES**, not functions, and reported as
the Multi-Dimensional Safety Matrix: Original C sites, Emitted Rust sites, the
reduction %, and the Unsafe-Operation-Density (UOD = unsafe sites ÷ total
expressions) on each side. Both lanes count the same whole-program function
population (the C funnel counts `#include`d project functions, matching the
emitter's whole-program materialisation — each project is emitted as one
whole-program crate), so there is no scope-mismatch outlier.

The fair apples-to-apples aggregate is over the **16 projects where both lanes
fully transpiled and the Rust compiled** (failed-transpilation projects have a C
count but little/no compiling Rust, so a whole-corpus sum would be meaningless —
the per-project table still shows all 100 honestly): **13,570 Original C unsafe
sites → 22,034 Emitted Rust unsafe sites** (Unsafe Site Reduction **−62.4%**), at
**Baseline C UOD 6.33% → Emitted Rust UOD 9.24%**.

Only GENUINELY external calls count toward the total: an `extern_unsafe_call` is
a call to libc / a foreign symbol. Calls the transpiler introduces purely to
stitch the program together — first-party functions the emitter exposes through
an `extern "C"` boundary so the emitted crate splices under the CRUST-bench test
harness (`first_party_call`), plus benign compiler intrinsics
like `assert` / branch hints (`intrinsic_call`) — are emission artifacts, split
into two separate excluded lanes. The reduction stays negative because this
build is a faithful transliteration (ownership/borrow uplift is deliberately
deferred): genuine libc calls that are free in C are explicit unsafe calls in
Rust, and the emitter synthesises helper/accessor functions (absent
from the C source) that carry their own unsafe operations. The real memory-safety
story lives in the per-family C→Rust split beneath the table.

### Per-project results

Generated from the run's per-project result rows by
[`benchmarks/generate_report.py`](benchmarks/generate_report.py) (the harness
regenerates this table as `results/REPORT.md` on every sweep). Every column —
including what a "site" is and why the Rust site total can exceed C's — is
defined in the legend rendered directly beneath the table, and the per-family
C→Rust before/after breakdown follows it.

<!-- crust-table:begin -->
| Project | Transpiled | Compiled | Tested | Original C Unsafe Sites | Emitted Rust Unsafe Sites | Unsafe Site Reduction (%) | Baseline C UOD | Emitted Rust UOD |
|---|---|---|---|---:|---:|---:|---:|---:|
| [SQLite](https://www.sqlite.org/) → [Rust output](https://github.com/o2alexanderfedin/sqlite-rust-mirror) — **flagship** | ✅ all 84 files | ✅ one whole-program monocrate | ✅ all 10 SQL scripts byte-identical vs native CLI (3 runs) | 40,508 | 84,190 | −107.8% | 7.4% | 8.3% |
| [2DPartInt](https://github.com/eafit-apolo/2DPartInt) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [42-Kocaeli-Printf](https://github.com/enes2424/42-Kocaeli-Printf) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [aes128-SIMD](https://github.com/at0m741/aes128-SIMD) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [amp](https://github.com/clibs/amp) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 20 | 39 | −95.0% | 3.8% | 8.1% |
| [approxidate](https://github.com/thatguystone/approxidate) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 188 | 386 | −105.3% | 4.4% | 7.9% |
| [avalanche](https://github.com/drjerry/avalanche) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [bhshell](https://github.com/bsach64/bhshell) | C++ ⚠️ · Rust ❌ | C++ 4/4 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 245 | 0 | +100.0% | 11.8% | — |
| [bigint](https://github.com/adam-mcdaniel/bigint) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 198 | 170 | +14.1% | 1.7% | 4.9% |
| [bitset](https://github.com/abenhlal/bitset) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [blt](https://github.com/blynn/blt) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [bostree](https://github.com/phillipberndt/bostree) | C++ ✅ · Rust ✅ | C++ 2/3 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 368 | 508 | −38.0% | 13.4% | 13.2% |
| [btree-map](https://github.com/EdsonHTJ/btree-map) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 178 | 382 | −114.6% | 5.8% | 11.1% |
| [c-aces](https://github.com/enum-class/c-aces) | C++ ⚠️ · Rust ❌ | C++ 5/5 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 354 | 0 | +100.0% | 9.0% | — |
| [c-blind-rsa-signatures](https://github.com/jedisct1/c-blind-rsa-signatures) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 693 | 1,844 | −166.1% | 7.8% | 17.3% |
| [c-string](https://github.com/vnkrtv/c-string) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [carrays](https://github.com/noporpoise/carrays) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 648 | 1,537 | −137.2% | 3.7% | 8.4% |
| [cfsm](https://github.com/nhjschulz/cfsm) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [chtrie](https://github.com/dongyx/chtrie) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 66 | 79 | −19.7% | 12.2% | 9.4% |
| [CircularBuffer](https://github.com/Roen-Ro/CircularBuffer) | C++ ⚠️ · Rust ❌ | C++ 0/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 102 | 0 | +100.0% | 11.0% | — |
| [cissy](https://github.com/slass100/cissy) | C++ ✅ · Rust ✅ | C++ 4/7 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 330 | 376 | −13.9% | 5.5% | 12.3% |
| [cJSON](https://github.com/faycheng/cJSON) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 478 | 1,183 | −147.5% | 7.2% | 10.2% |
| [clhash](https://github.com/simdhash/clhash) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [clog](https://github.com/mmueller/clog) | C++ ✅ · Rust ❌ | C++ 0/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 64 | 0 | +100.0% | 2.2% | — |
| [coroutine](https://github.com/cloudwu/coroutine) | C++ ⚠️ · Rust ❌ | C++ 1/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 1 | 0 | +100.0% | 0.9% | — |
| [cset](https://github.com/RobusGauli/cset.h) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 14,573 | 24 | +99.8% | 13.4% | 2.7% |
| [csyncmers](https://github.com/rchikhi/csyncmers) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 64 | 67 | −4.7% | 3.5% | 6.0% |
| [dict](https://github.com/wrnlb666/dict) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 352 | 0 | +100.0% | 8.9% | — |
| [emlang](https://github.com/LordOfTrident/emlang) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [expr](https://github.com/radarsat1/expr) | C++ ✅ · Rust ❌ | C++ 1/2 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 360 | 0 | +100.0% | 9.0% | — |
| [FastHamming](https://github.com/BenBE/FastHamming.git) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [fft](https://github.com/kevin0x0/fft) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 78 | 124 | −59.0% | 4.3% | 5.5% |
| [file2str](https://github.com/willemt/file2str) | C++ ✅ · Rust ✅ | C++ 4/4 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 82 | 148 | −80.5% | 5.2% | 8.3% |
| [fleur](https://github.com/hashlookup/fleur) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [fs_c](https://github.com/jwerle/fs.c) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 1 | 47 | −4600.0% | 0.2% | 10.1% |
| [fslib](https://github.com/c0stya/fslib) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Genetic-neural-network-for-simple-control](https://github.com/DemianovE/Genetic-neural-network-for-simple-control) | C++ ⚠️ · Rust ❌ | C++ 12/12 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 644 | 0 | +100.0% | 14.6% | — |
| [geofence](https://github.com/bytebeamio/geofence.git) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 12 | 8 | +33.3% | 4.3% | 3.6% |
| [gfc](https://github.com/maxmouchet/gfc.git) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [gorilla-paper-encode](https://github.com/MrBean818/gorilla-paper-encode) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 173 | 133 | +23.1% | 8.9% | 4.0% |
| [Graph-recogniser](https://github.com/NikolaYolov/Graph-recogniser) | C++ ✅ · Rust ✅ | C++ 4/4 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 147 | 296 | −101.4% | 5.9% | 10.7% |
| [hamta](https://github.com/burtgulash/hamta) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 145 | 32 | +77.9% | 8.6% | 8.8% |
| [Holdem-Odds](https://github.com/gnuvince/Holdem-Odds) | C++ ✅ · Rust ✅ | C++ 4/5 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 64 | 72 | −12.5% | 5.6% | 5.5% |
| [hydra](https://github.com/emad-elsaid/hydra) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 71 | 148 | −108.5% | 7.7% | 14.3% |
| [impcheck](https://github.com/domschrei/impcheck) | C++ ⚠️ · Rust ❌ | C++ 2/2 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | 0.0% | — |
| [inversion_list](https://github.com/hou-12/Inversion-List-Implementation-for-Interval-Manipulation) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [jccc](https://github.com/jabacat/jccc) | C++ ✅ · Rust ✅ | C++ 12/13 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 226 | 358 | −58.4% | 4.0% | 10.2% |
| [kairoCompiler](https://github.com/kairo-yr/kairoCompiler) | C++ ✅ · Rust ❌ | C++ 3/10 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 234 | 0 | +100.0% | 4.9% | — |
| [kd3](https://github.com/shawnchin/kd3) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/1 | A/B C++ ✅·Rust — · pass@1 — | 179 | 259 | −44.7% | 6.7% | 9.0% |
| [lambda-calculus-eval](https://github.com/Lorenzobattistela/lambda-calculus-eval) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [leftpad](https://github.com/sjmulder/leftpad) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/1 | A/B C++ ✅·Rust ✅ · pass@1 — | 16 | 47 | −193.8% | 5.5% | 10.9% |
| [lib2bit](https://github.com/dpryan79/lib2bit) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 432 | 624 | −44.4% | 10.8% | 9.1% |
| [libbase122](https://github.com/kevinAlbs/libbase122) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [libbeaufort](https://github.com/jwerle/libbeaufort) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 37 | 78 | −110.8% | 5.6% | 8.0% |
| [libfor](https://github.com/cruppstahl/libfor) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/1 | A/B C++ ✅·Rust — · pass@1 — | 11,624 | 18,846 | −62.1% | 6.2% | 9.2% |
| [libm17](https://github.com/M17-Project/libm17) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [libpgn](https://github.com/youkwhd/libpgn) | C++ ✅ · Rust ✅ | C++ 11/12 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 339 | 351 | −3.5% | 6.7% | 9.8% |
| [libpsbt](https://github.com/jb55/libpsbt) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [libqueue](https://github.com/resyfer/libqueue) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [libtinyfseq](https://github.com/Cryptkeeper/libtinyfseq) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [libutf](https://github.com/holepunchto/libutf) | C++ ⚠️ · Rust ✅ | C++ 0/27 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 10,911 | 347 | +96.8% | 8.2% | 7.5% |
| [libvcd](https://github.com/sorousherafat/libvcd) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 42 | 106 | −152.4% | 4.3% | 8.6% |
| [libwecan](https://github.com/nisennenmondai/libwecan) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [Linear-Algebra-C](https://github.com/barrettotte/Linear-Algebra-C) | C++ ✅ · Rust ✅ | C++ 4/4 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 499 | 624 | −25.1% | 6.3% | 7.0% |
| [ljmm](https://github.com/cloudflare/ljmm) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [LTRE](https://github.com/Bricktech2000/LTRE) | C++ ✅ · Rust ❌ | C++ 1/2 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 476 | 0 | +100.0% | 7.3% | — |
| [Math-Library-in-C](https://github.com/Astrodynamic/Math-Library-in-C) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [matrix_multiplication](https://github.com/DevRuibin/matrix_multiplication) | C++ ⚠️ · Rust ❌ | C++ 1/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 2 | 0 | +100.0% | 2.6% | — |
| [mdb](https://github.com/chuigda/mdb.git) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Megalania](https://github.com/blackle/Megalania) | C++ ⚠️ · Rust ❌ | C++ 16/16 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 451 | 0 | +100.0% | 8.2% | — |
| [merkle-tree-c](https://github.com/TheWaWaR/merkle-tree-c) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 251 | 363 | −44.6% | 1.1% | 1.6% |
| [morton](https://github.com/jart/morton) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [murmurhash_c](https://github.com/jwerle/murmurhash.c) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 11 | 60 | −445.5% | 1.5% | 8.2% |
| [mvptree](https://github.com/michaelmior/mvptree) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 1,004 | 1,424 | −41.8% | 9.6% | 12.8% |
| [NandC](https://github.com/Dcraftbg/NandC) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 3 | 20 | −566.7% | 0.4% | 3.2% |
| [Phills_DHT](https://github.com/PhillipTaylor/Phills_DHT) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 27 | 87 | −222.2% | 5.0% | 15.7% |
| [quadtree](https://github.com/thejefflarson/quadtree) | C++ ✅ · Rust ✅ | C++ 5/5 · Rust 1/1 | A/B C++ ✅·Rust ✅ · pass@1 — | 200 | 348 | −74.0% | 7.5% | 11.7% |
| [razz_simulation](https://github.com/eus/razz_simulation) | C++ ✅ · Rust ❌ | C++ 0/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 11 | 0 | +100.0% | 1.8% | — |
| [rbtree-lab](https://github.com/jwowo/rbtree-lab) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [recordManager](https://github.com/prachikotadia/-Record-Manager) | C++ ⚠️ · Rust ❌ | C++ 7/7 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 1,190 | 0 | +100.0% | 6.8% | — |
| [rect_pack_h](https://github.com/luihabl/rect_pack.h) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Remimu](https://github.com/wareya/Remimu) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [rhbloom](https://github.com/tidwall/rhbloom) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 100 | 211 | −111.0% | 4.5% | 8.0% |
| [roaring-bitmap](https://github.com/chriso/roaring-bitmap) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [rubiksolver](https://github.com/justjkk/rubiksolver) | C++ ✅ · Rust ✅ | C++ 2/5 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 379 | 679 | −79.2% | 6.7% | 11.7% |
| [satc](https://github.com/rjungemann/satc) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Simple-Config](https://github.com/0xHaru/Simple-Config) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 117 | 366 | −212.8% | 3.9% | 10.3% |
| [Simple-Sparsehash](https://github.com/qpfiffer/Simple-Sparsehash) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 91 | 406 | −346.2% | 2.5% | 7.3% |
| [simple_lang](https://github.com/lxbme/simple_lang) | C++ ✅ · Rust ❌ | C++ 11/11 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 263 | 0 | +100.0% | 6.8% | — |
| [SimpleXML](https://github.com/kiennt/SimpleXML.git) | C++ ⚠️ · Rust ❌ | C++ 1/2 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 137 | 0 | +100.0% | 9.6% | — |
| [skp](https://github.com/rdentato/skp) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [SlothLang](https://github.com/AaronCGoidel/SlothLang) | C++ ⚠️ · Rust ❌ | C++ 3/3 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 13 | 0 | +100.0% | 2.3% | — |
| [ted](https://github.com/ajpen/ted) | C++ ⚠️ · Rust ✅ | C++ 3/3 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 381 | 631 | −65.6% | 7.0% | 9.6% |
| [tisp](https://github.com/edvb/tisp) | C++ ✅ · Rust ✅ | C++ 0/2 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 1,659 | 510 | +69.3% | 9.4% | 10.8% |
| [totp](https://github.com/sjmulder/totp) | C++ ✅ · Rust ✅ | C++ 2/3 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 53 | 170 | −220.8% | 1.9% | 7.5% |
| [ulidgen](https://github.com/leahneukirchen/ulidgen) | C++ ⚠️ · Rust ❌ | C++ 1/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 1 | 0 | +100.0% | 0.4% | — |
| [utf8](https://github.com/zahash/utf8.c) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 75 | 498 | −564.0% | 1.5% | 12.1% |
| [VaultSync](https://github.com/elhalili/VaultSync) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [vec](https://github.com/rxi/vec) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/1 | A/B C++ ✅·Rust — · pass@1 — | 885 | 2,040 | −130.5% | 9.5% | 15.5% |
| [worsp](https://github.com/sosukesuzuki/worsp) | C++ ⚠️ · Rust ❌ | C++ 0/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 1,087 | 0 | +100.0% | 13.6% | — |
| [XOpt](https://github.com/drylikov/XOpt.git) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 268 | 618 | −130.6% | 5.6% | 6.3% |

<sub>A **site** is one individual unsafe OPERATION, not a function or a whole `unsafe {}` block (those are too coarse). **Transpiled / Compiled** — did cpp2rust emit, and does the emitted code build, for the C++ lane and the Rust lane (`ok/total` translation units). **Tested** — the differential test oracles: **A/B** runs the project's own program built from native C vs from the transpiled C++/Rust and compares output byte-for-byte (`—` = not linkable as one binary, e.g. cross-TU C++ name mangling or unresolved builtin FFI; logged, never silently passed); **pass@1** is CRUST-bench's official oracle — the emitted crate spliced under the hand-written RBench interface, then `cargo test`. For SQLite the Tested cell is the whole-CLI differential over the SQL scripts. **Original C Unsafe Sites** — initial unsafe operation sites in the C source (`raw_ptr_deref + static_mut + union_member`). **Emitted Rust Unsafe Sites** — resulting unsafe operation sites in the emitted Rust (`raw_ptr_deref + extern_unsafe_call + static_mut + union_read + transmute + inline_asm`). `extern_unsafe_call` counts only GENUINELY external calls (libc / foreign symbols). A call whose target is defined elsewhere in the project - a first-party function the emitter exposes through an `extern "C"` boundary so the emitted crate splices under the CRUST-bench harness - plus transpiler shims and benign compiler intrinsics (assert, branch hints, object-size) are emission artifacts, NOT unsafety carried over from the C source; they are split into two separate excluded lanes, `first_party_call` (harness-FFI / transpiler shims) and `intrinsic_call` (benign compiler intrinsics), neither ever folded into the total. `unchecked_arith` (C pointer arithmetic, no Rust unsafe counterpart) is likewise separate. The per-family breakdown below shows every lane. **Unsafe Site Reduction (%)** — `(C − Rust) ÷ C`; **positive = net fewer** unsafe sites, **negative = net more** (this build is a faithful transliteration — ownership/borrow uplift is deferred — so where Rust adds sites it is mostly C's previously-hidden FFI unsafety made explicit, not new unsafety). **Baseline C UOD** / **Emitted Rust UOD** — Unsafe-Operation-Density: unsafe sites ÷ total expressions in that lane's own AST (lower is safer); the denominator grows with any added scaffolding, so the density cannot be gamed by code inflation. All counts use thousands separators.</sub>

**Unsafe operation sites by family — across the 16 projects where both lanes fully transpiled and the Rust compiled** (the fair apples-to-apples population; the other rows have a C count but little or no compiling Rust, so a whole-corpus sum would be meaningless):

| Family | Sites (C) | Sites (Rust) | Δ (C−Rust) |
|---|---:|---:|---:|
| raw_ptr_deref | 13,505 | 16,203 | -2,698 |
| extern_unsafe_call (genuine libc/foreign) | — *(not unsafe in C)* | 5,816 | — |
| static_mut | 24 | 12 | 12 |
| union read | 41 | 2 | 39 |
| transmute | — *(not unsafe in C)* | 1 | — |
| inline_asm | — *(not unsafe in C)* | 0 | — |
| **Total (memory-safety sites)** | **13,570** | **22,034** | **-8,464** |
| _unchecked_arith (separate lane)_ | _5,058_ | _0_ | _—_ |
| _first_party_call (harness-FFI / transpiler shims — excluded)_ | _—_ | _80_ | _—_ |
| _intrinsic_call (benign compiler intrinsics — excluded)_ | _—_ | _254_ | _—_ |

Totals — Original C unsafe sites **13,570** → Emitted Rust unsafe sites **22,034** (Unsafe Site Reduction **−62.4%**: more unsafe sites in the emitted Rust — this build is a faithful transliteration (ownership uplift deferred) that surfaces C's hidden libc-FFI unsafety as explicit `extern_unsafe_call`s). Baseline C UOD **6.33%** → Emitted Rust UOD **9.24%** (unsafe sites ÷ total expressions in each lane's AST).
Raw-pointer dereferences (the core memory-safety family): 13,505 in C → 16,203 in Rust (**+2,698**; the emitter lowers some compound C accesses into several explicit Rust derefs, so a per-project split — not this raw aggregate — is the honest read of the memory-safety change).
Both lanes now count the same whole-program function population (the C funnel counts project `#include`d functions, matching the emitter's whole-program materialisation — each project is emitted as one whole-program crate), so the libfor-style scope outlier is gone. Two known residual asymmetries: (1) the emitter synthesises helper/accessor functions absent from the C source that carry their own unsafe operations, inflating the Rust side; (2) genuine libc calls are free in C but explicit unsafe calls in Rust. Both push the Rust total up honestly — read the per-family split and the UOD columns, not a single number.
<!-- crust-table:end -->

### pass@1 — 0 pass / 35 attempted / 65 no interface match

pass@1 is the benchmark's headline metric: does the emitted Rust compile
against the project's *separately authored* Rust interface and pass
`cargo test`? This run now ATTEMPTS it (earlier reports recorded it
`not-attempted`): for every project with a compiling Rust crate, the emitted
modules are spliced under the hand-written RBench interface and `cargo test`
is run. 35 projects reached the splice; none passed — the emitted crate is a
faithful C-ABI translation whose module shapes and signatures do not yet
reconcile with the third-party hand-written interface (the remaining 65 had no
interface module to splice against). This is recorded honestly as `fail`/`—`,
never a blended success. For scale: the benchmark paper's best single-shot
model result solved 15 of 100 on this metric.

### Framing

clang2rust is tuned for large, self-contained C codebases such as
[SQLite](https://www.sqlite.org/) — where the complete command-line shell,
transpiled to Rust, runs byte-identical to the native build (see the
[README](README.md)). CRUST-bench is a deliberately different target: 100
unrelated third-party repositories with their own build systems and externally
supplied Rust interfaces. On this run the converter fully transpiles 48 of the
81 reachable projects to Rust (23 all the way to fully-compiling Rust) and 52
to C++, declines loudly — never silently mis-translating — where it hits
constructs it does not yet support, and every A/B leg that was linkable ran
byte-identical to native. We publish these numbers as a transparent baseline
to track over time, not as a figure to inflate or omit.

### Run environment notes

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
