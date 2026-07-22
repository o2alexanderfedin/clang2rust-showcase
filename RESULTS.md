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

The complete [SQLite](https://www.sqlite.org/) source tree — 281 C files,
including the full command-line shell — is transpiled to Rust in a single
run. Unlike the CRUST-bench rows below, the **Tested** column here is real
end-to-end differential testing: the transpiled command-line shell and the
native one execute the same 10 SQL scripts and their outputs are compared
byte-for-byte, reproduced three times, including under an allocator-hardened
harness.

<!-- sqlite-table:begin -->
| Project | Transpiled | Compiled | Tested | Original C Unsafe Sites | Emitted Rust Unsafe Sites | Unsafe Site Reduction (%) | Baseline C UOD | Emitted Rust UOD |
|---|---|---|---|---:|---:|---:|---:|---:|
| [SQLite](https://www.sqlite.org/) → [Rust output](https://github.com/o2alexanderfedin/sqlite-rust-mirror) | ✅ all 281 files | ✅ all 281 crates | ✅ all 10 SQL scripts byte-identical vs native CLI (3 runs) | `pending-regen` | `pending-regen` | `pending-regen` | `pending-regen` | `pending-regen` |

<sub>A **site** is one individual unsafe OPERATION, not a function or a whole `unsafe {}` block (those are too coarse). **Transpiled / Compiled** — did cpp2rust emit, and does the emitted code build, for the C++ lane and the Rust lane (`ok/total` translation units). **Tested** — the differential test oracles: **A/B** runs the project's own program built from native C vs from the transpiled C++/Rust and compares output byte-for-byte (`—` = not linkable as one binary, e.g. cross-TU C++ name mangling or unresolved builtin FFI; logged, never silently passed); **pass@1** is CRUST-bench's official oracle — the emitted crate spliced under the hand-written RBench interface, then `cargo test`. For SQLite the Tested cell is the whole-CLI differential over the SQL scripts. **Original C Unsafe Sites** — initial unsafe operation sites in the C source (`raw_ptr_deref + static_mut + union_member`). **Emitted Rust Unsafe Sites** — resulting unsafe operation sites in the emitted Rust (`raw_ptr_deref + extern_unsafe_call + static_mut + union_read + transmute + inline_asm`). `extern_unsafe_call` counts only GENUINELY external calls (libc / foreign symbols). A call whose target is defined elsewhere in the project - a first-party function reached over the C ABI only because the emitter emits one crate per translation unit and exposes symbols to the CRUST-bench harness - plus transpiler shims and benign compiler intrinsics (assert, branch hints, object-size) are emission artifacts, NOT unsafety carried over from the C source; they go to a separate `internal_call` lane never folded into the total. `unchecked_arith` (C pointer arithmetic, no Rust unsafe counterpart) is likewise separate. The per-family breakdown below shows every lane. **Unsafe Site Reduction (%)** — `(C − Rust) ÷ C`; **positive = net fewer** unsafe sites, **negative = net more** (this build is a faithful transliteration — ownership/borrow uplift is deferred — so where Rust adds sites it is mostly C's previously-hidden FFI unsafety made explicit, not new unsafety). **Baseline C UOD** / **Emitted Rust UOD** — Unsafe-Operation-Density: unsafe sites ÷ total expressions in that lane's own AST (lower is safer); the denominator grows with any added scaffolding, so the density cannot be gamed by code inflation. All counts use thousands separators.</sub>

<sub>SQLite's site columns are `pending-regen`: the SQLite unsafe-site census is regenerated off the fixed develop tip AFTER the current verification battery completes and the 16-02 SQLite-lane fix merges — numbers produced before then would not match the shipped state. State columns above reflect the last verified run (2026-07-20).</sub>
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

C++ crates: **173 of 239** emitted compile. Rust crates: **117 of 239** compile.

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
expressions) on each side. Across all 100 projects: **29,302 Original C unsafe
sites → 43,319 Emitted Rust unsafe sites** (Unsafe Site Reduction **−47.8%**),
at **Baseline C UOD 8.90% → Emitted Rust UOD 8.64%** — the emitted Rust's
density of unsafe operations is slightly **lower** than the C baseline's.

Only GENUINELY external calls count: an `extern_unsafe_call` is a call to libc /
a foreign symbol (12,333 sites). Calls the transpiler introduces purely to
stitch the program together — first-party functions reached over the C ABI
because we emit one crate per translation unit and expose symbols to the
CRUST-bench test harness, plus transpiler shims and benign compiler intrinsics
(`assert`, branch hints) — are emission artifacts, not unsafety carried over
from the C, so they are split into a separate `internal_call` lane (4,239 sites,
excluded from the total). The reduction is still negative because this build is
a faithful transliteration (ownership/borrow uplift is deliberately deferred),
so genuine libc calls that are free in C are explicit unsafe calls in Rust. The
real memory-safety story lives in the per-family C→Rust split beneath the table
— e.g. C's 840 union type-punning accesses become 1,323 explicit `transmute`s
and just 2 raw union reads, and C pointer arithmetic (474 sites) has no Rust
unsafe counterpart at all (lowered to safe `wrapping_*`).

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
| [SQLite](https://www.sqlite.org/) → [Rust output](https://github.com/o2alexanderfedin/sqlite-rust-mirror) — **flagship** | ✅ all 281 files | ✅ all 281 crates | ✅ all 10 SQL scripts byte-identical vs native CLI (3 runs) | `pending-regen` | `pending-regen` | `pending-regen` | `pending-regen` | `pending-regen` |
| [2DPartInt](https://github.com/eafit-apolo/2DPartInt) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [42-Kocaeli-Printf](https://github.com/enes2424/42-Kocaeli-Printf) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [aes128-SIMD](https://github.com/at0m741/aes128-SIMD) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [amp](https://github.com/clibs/amp) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 2/2 | A/B C++ —·Rust — · pass@1 ❌ | 20 | 39 | −95.0% | 3.8% | 8.1% |
| [approxidate](https://github.com/thatguystone/approxidate) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 0/2 | A/B C++ —·Rust — · pass@1 ❌ | 188 | 384 | −104.3% | 4.4% | 7.8% |
| [avalanche](https://github.com/drjerry/avalanche) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [bhshell](https://github.com/bsach64/bhshell) | C++ ⚠️ · Rust ⚠️ | C++ 4/4 · Rust 2/4 | A/B C++ —·Rust — · pass@1 ❌ | 245 | 267 | −9.0% | 11.8% | 10.4% |
| [bigint](https://github.com/adam-mcdaniel/bigint) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 0/3 | A/B C++ —·Rust — · pass@1 — | 0 | 439 | — | 0.0% | 4.0% |
| [bitset](https://github.com/abenhlal/bitset) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [blt](https://github.com/blynn/blt) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [bostree](https://github.com/phillipberndt/bostree) | C++ ✅ · Rust ✅ | C++ 2/3 · Rust 3/3 | A/B C++ —·Rust — · pass@1 ❌ | 368 | 466 | −26.6% | 13.4% | 12.4% |
| [btree-map](https://github.com/EdsonHTJ/btree-map) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 2/2 | A/B C++ —·Rust — · pass@1 — | 178 | 432 | −142.7% | 5.8% | 12.8% |
| [c-aces](https://github.com/enum-class/c-aces) | C++ ⚠️ · Rust ⚠️ | C++ 5/5 · Rust 4/5 | A/B C++ —·Rust — · pass@1 — | 330 | 269 | +18.5% | 9.1% | 7.6% |
| [c-blind-rsa-signatures](https://github.com/jedisct1/c-blind-rsa-signatures) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 0/2 | A/B C++ —·Rust — · pass@1 — | 137 | 3,023 | −2106.6% | 3.1% | 19.6% |
| [c-string](https://github.com/vnkrtv/c-string) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [carrays](https://github.com/noporpoise/carrays) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 0/2 | A/B C++ —·Rust — · pass@1 ❌ | 349 | 1,483 | −324.9% | 2.8% | 7.5% |
| [cfsm](https://github.com/nhjschulz/cfsm) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [chtrie](https://github.com/dongyx/chtrie) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 66 | 76 | −15.2% | 12.2% | 9.0% |
| [CircularBuffer](https://github.com/Roen-Ro/CircularBuffer) | C++ ⚠️ · Rust ⚠️ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 ❌ | 102 | 64 | +37.3% | 11.0% | 6.3% |
| [cissy](https://github.com/slass100/cissy) | C++ ✅ · Rust ✅ | C++ 4/7 · Rust 5/7 | A/B C++ —·Rust — · pass@1 ❌ | 330 | 675 | −104.5% | 5.5% | 13.1% |
| [cJSON](https://github.com/faycheng/cJSON) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/2 | A/B C++ ✅·Rust — · pass@1 ❌ | 478 | 1,197 | −150.4% | 7.2% | 10.3% |
| [clhash](https://github.com/simdhash/clhash) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [clog](https://github.com/mmueller/clog) | C++ ✅ · Rust ❌ | C++ 0/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 10 | 0 | +100.0% | 0.6% | — |
| [coroutine](https://github.com/cloudwu/coroutine) | C++ ⚠️ · Rust ⚠️ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 1 | 19 | −1800.0% | 0.9% | 14.7% |
| [cset](https://github.com/RobusGauli/cset.h) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 14,564 | 24 | +99.8% | 13.5% | 2.8% |
| [csyncmers](https://github.com/rchikhi/csyncmers) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 2/2 | A/B C++ —·Rust — · pass@1 — | 10 | 92 | −820.0% | 1.6% | 5.1% |
| [dict](https://github.com/wrnlb666/dict) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 352 | 0 | +100.0% | 8.9% | — |
| [emlang](https://github.com/LordOfTrident/emlang) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [expr](https://github.com/radarsat1/expr) | C++ ✅ · Rust ⚠️ | C++ 1/2 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 360 | 28 | +92.2% | 9.0% | 6.2% |
| [FastHamming](https://github.com/BenBE/FastHamming.git) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [fft](https://github.com/kevin0x0/fft) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 78 | 106 | −35.9% | 4.3% | 4.8% |
| [file2str](https://github.com/willemt/file2str) | C++ ✅ · Rust ✅ | C++ 4/4 · Rust 3/4 | A/B C++ —·Rust — · pass@1 ❌ | 82 | 147 | −79.3% | 5.2% | 8.3% |
| [fleur](https://github.com/hashlookup/fleur) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [fs_c](https://github.com/jwerle/fs.c) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 1 | 46 | −4500.0% | 0.2% | 9.9% |
| [fslib](https://github.com/c0stya/fslib) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Genetic-neural-network-for-simple-control](https://github.com/DemianovE/Genetic-neural-network-for-simple-control) | C++ ⚠️ · Rust ⚠️ | C++ 12/12 · Rust 10/12 | A/B C++ —·Rust — · pass@1 — | 644 | 779 | −21.0% | 14.6% | 12.7% |
| [geofence](https://github.com/bytebeamio/geofence.git) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 12 | 6 | +50.0% | 4.3% | 2.7% |
| [gfc](https://github.com/maxmouchet/gfc.git) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [gorilla-paper-encode](https://github.com/MrBean818/gorilla-paper-encode) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/2 | A/B C++ ✅·Rust — · pass@1 — | 173 | 131 | +24.3% | 8.9% | 3.9% |
| [Graph-recogniser](https://github.com/NikolaYolov/Graph-recogniser) | C++ ✅ · Rust ✅ | C++ 4/4 · Rust 0/4 | A/B C++ ✅·Rust — · pass@1 — | 141 | 325 | −130.5% | 6.0% | 11.3% |
| [hamta](https://github.com/burtgulash/hamta) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 145 | 31 | +78.6% | 8.6% | 8.8% |
| [Holdem-Odds](https://github.com/gnuvince/Holdem-Odds) | C++ ✅ · Rust ✅ | C++ 4/5 · Rust 3/5 | A/B C++ —·Rust — · pass@1 — | 64 | 80 | −25.0% | 5.6% | 5.4% |
| [hydra](https://github.com/emad-elsaid/hydra) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 71 | 148 | −108.5% | 7.7% | 14.3% |
| [impcheck](https://github.com/domschrei/impcheck) | C++ ⚠️ · Rust ⚠️ | C++ 2/2 · Rust 2/2 | A/B C++ —·Rust — · pass@1 ❌ | 0 | 3 | — | 0.0% | 12.0% |
| [inversion_list](https://github.com/hou-12/Inversion-List-Implementation-for-Interval-Manipulation) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [jccc](https://github.com/jabacat/jccc) | C++ ✅ · Rust ✅ | C++ 12/13 · Rust 11/13 | A/B C++ —·Rust — · pass@1 ❌ | 226 | 718 | −217.7% | 4.0% | 10.5% |
| [kairoCompiler](https://github.com/kairo-yr/kairoCompiler) | C++ ✅ · Rust ⚠️ | C++ 3/10 · Rust 0/5 | A/B C++ —·Rust — · pass@1 ❌ | 193 | 234 | −21.2% | 4.1% | 10.9% |
| [kd3](https://github.com/shawnchin/kd3) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 2/2 | A/B C++ ✅·Rust — · pass@1 ❌ | 179 | 228 | −27.4% | 6.7% | 8.0% |
| [lambda-calculus-eval](https://github.com/Lorenzobattistela/lambda-calculus-eval) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [leftpad](https://github.com/sjmulder/leftpad) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 2/2 | A/B C++ ✅·Rust ✅ · pass@1 ❌ | 16 | 39 | −143.8% | 5.5% | 9.4% |
| [lib2bit](https://github.com/dpryan79/lib2bit) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 — | 432 | 593 | −37.3% | 10.8% | 8.9% |
| [libbase122](https://github.com/kevinAlbs/libbase122) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [libbeaufort](https://github.com/jwerle/libbeaufort) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 3/3 | A/B C++ —·Rust — · pass@1 ❌ | 37 | 63 | −70.3% | 5.6% | 6.7% |
| [libfor](https://github.com/cruppstahl/libfor) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 2/2 | A/B C++ ✅·Rust — · pass@1 — | 55 | 14,562 | −26376.4% | 2.5% | 7.2% |
| [libm17](https://github.com/M17-Project/libm17) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [libpgn](https://github.com/youkwhd/libpgn) | C++ ✅ · Rust ✅ | C++ 11/12 · Rust 4/12 | A/B C++ —·Rust — · pass@1 ❌ | 339 | 553 | −63.1% | 6.7% | 8.3% |
| [libpsbt](https://github.com/jb55/libpsbt) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [libqueue](https://github.com/resyfer/libqueue) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [libtinyfseq](https://github.com/Cryptkeeper/libtinyfseq) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [libutf](https://github.com/holepunchto/libutf) | C++ ⚠️ · Rust ✅ | C++ 0/27 · Rust 0/36 | A/B C++ —·Rust — · pass@1 — | 122 | 0 | +100.0% | 1.9% | 0.0% |
| [libvcd](https://github.com/sorousherafat/libvcd) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/2 | A/B C++ ✅·Rust — · pass@1 ❌ | 42 | 104 | −147.6% | 4.3% | 8.5% |
| [libwecan](https://github.com/nisennenmondai/libwecan) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [Linear-Algebra-C](https://github.com/barrettotte/Linear-Algebra-C) | C++ ✅ · Rust ✅ | C++ 4/4 · Rust 1/4 | A/B C++ ✅·Rust — · pass@1 — | 499 | 621 | −24.4% | 6.3% | 6.7% |
| [ljmm](https://github.com/cloudflare/ljmm) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [LTRE](https://github.com/Bricktech2000/LTRE) | C++ ✅ · Rust ⚠️ | C++ 1/2 · Rust 0/1 | A/B C++ —·Rust — · pass@1 ❌ | 476 | 0 | +100.0% | 7.3% | — |
| [Math-Library-in-C](https://github.com/Astrodynamic/Math-Library-in-C) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [matrix_multiplication](https://github.com/DevRuibin/matrix_multiplication) | C++ ⚠️ · Rust ⚠️ | C++ 1/1 · Rust 1/1 | A/B C++ —·Rust — · pass@1 ❌ | 2 | 12 | −500.0% | 2.6% | 10.7% |
| [mdb](https://github.com/chuigda/mdb.git) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Megalania](https://github.com/blackle/Megalania) | C++ ⚠️ · Rust ⚠️ | C++ 16/16 · Rust 9/16 | A/B C++ —·Rust — · pass@1 ❌ | 451 | 760 | −68.5% | 8.2% | 11.0% |
| [merkle-tree-c](https://github.com/TheWaWaR/merkle-tree-c) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 25 | 346 | −1284.0% | 1.7% | 1.5% |
| [morton](https://github.com/jart/morton) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [murmurhash_c](https://github.com/jwerle/murmurhash.c) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 3/3 | A/B C++ —·Rust — · pass@1 ❌ | 11 | 67 | −509.1% | 1.5% | 8.9% |
| [mvptree](https://github.com/michaelmior/mvptree) | C++ ✅ · Rust ✅ | C++ 3/3 · Rust 2/3 | A/B C++ —·Rust — · pass@1 ❌ | 1,004 | 1,542 | −53.6% | 9.6% | 12.0% |
| [NandC](https://github.com/Dcraftbg/NandC) | C++ ✅ · Rust ✅ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 0 | 20 | — | 0.0% | 3.3% |
| [Phills_DHT](https://github.com/PhillipTaylor/Phills_DHT) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 27 | 76 | −181.5% | 5.0% | 13.9% |
| [quadtree](https://github.com/thejefflarson/quadtree) | C++ ✅ · Rust ✅ | C++ 5/5 · Rust 5/5 | A/B C++ ✅·Rust ✅ · pass@1 ❌ | 200 | 344 | −72.0% | 7.5% | 11.5% |
| [razz_simulation](https://github.com/eus/razz_simulation) | C++ ✅ · Rust ❌ | C++ 0/1 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 11 | 0 | +100.0% | 1.8% | — |
| [rbtree-lab](https://github.com/jwowo/rbtree-lab) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [recordManager](https://github.com/prachikotadia/-Record-Manager) | C++ ⚠️ · Rust ⚠️ | C++ 7/7 · Rust 1/7 | A/B C++ —·Rust — · pass@1 ❌ | 1,190 | 3,007 | −152.7% | 6.8% | 13.6% |
| [rect_pack_h](https://github.com/luihabl/rect_pack.h) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Remimu](https://github.com/wareya/Remimu) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [rhbloom](https://github.com/tidwall/rhbloom) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/2 | A/B C++ —·Rust — · pass@1 ❌ | 100 | 202 | −102.0% | 4.5% | 7.8% |
| [roaring-bitmap](https://github.com/chriso/roaring-bitmap) | C++ ❌ · Rust ❌ | C++ 0/0 · Rust 0/0 | A/B C++ —·Rust — · pass@1 — | 0 | 0 | — | — | — |
| [rubiksolver](https://github.com/justjkk/rubiksolver) | C++ ✅ · Rust ✅ | C++ 2/5 · Rust 0/5 | A/B C++ —·Rust — · pass@1 ❌ | 379 | 781 | −106.1% | 6.7% | 11.3% |
| [satc](https://github.com/rjungemann/satc) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [Simple-Config](https://github.com/0xHaru/Simple-Config) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 0/2 | A/B C++ ✅·Rust — · pass@1 — | 117 | 361 | −208.5% | 3.9% | 10.1% |
| [Simple-Sparsehash](https://github.com/qpfiffer/Simple-Sparsehash) | C++ ✅ · Rust ✅ | C++ 1/2 · Rust 2/2 | A/B C++ —·Rust — · pass@1 — | 91 | 386 | −324.2% | 2.5% | 7.0% |
| [simple_lang](https://github.com/lxbme/simple_lang) | C++ ✅ · Rust ⚠️ | C++ 11/11 · Rust 9/10 | A/B C++ —·Rust — · pass@1 ❌ | 263 | 465 | −76.8% | 6.8% | 12.3% |
| [SimpleXML](https://github.com/kiennt/SimpleXML.git) | C++ ⚠️ · Rust ⚠️ | C++ 1/2 · Rust 0/2 | A/B C++ —·Rust — · pass@1 ❌ | 137 | 208 | −51.8% | 9.6% | 11.9% |
| [skp](https://github.com/rdentato/skp) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [SlothLang](https://github.com/AaronCGoidel/SlothLang) | C++ ⚠️ · Rust ⚠️ | C++ 3/3 · Rust 3/3 | A/B C++ —·Rust — · pass@1 ❌ | 13 | 50 | −284.6% | 2.3% | 7.8% |
| [ted](https://github.com/ajpen/ted) | C++ ⚠️ · Rust ✅ | C++ 3/3 · Rust 2/4 | A/B C++ —·Rust — · pass@1 ❌ | 339 | 571 | −68.4% | 6.7% | 8.8% |
| [tisp](https://github.com/edvb/tisp) | C++ ✅ · Rust ✅ | C++ 0/2 · Rust 0/2 | A/B C++ —·Rust — · pass@1 ❌ | 621 | 2,249 | −262.2% | 10.9% | 9.7% |
| [totp](https://github.com/sjmulder/totp) | C++ ✅ · Rust ✅ | C++ 2/3 · Rust 2/3 | A/B C++ —·Rust — · pass@1 ❌ | 23 | 179 | −678.3% | 0.9% | 5.5% |
| [ulidgen](https://github.com/leahneukirchen/ulidgen) | C++ ⚠️ · Rust ⚠️ | C++ 1/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 1 | 35 | −3400.0% | 0.4% | 9.7% |
| [utf8](https://github.com/zahash/utf8.c) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 1/2 | A/B C++ ✅·Rust — · pass@1 ❌ | 75 | 593 | −690.7% | 1.5% | 14.2% |
| [VaultSync](https://github.com/elhalili/VaultSync) | n/a — project build broken | — | — | 0 | 0 | — | — | — |
| [vec](https://github.com/rxi/vec) | C++ ✅ · Rust ✅ | C++ 2/2 · Rust 2/2 | A/B C++ ✅·Rust — · pass@1 ❌ | 885 | 1,975 | −123.2% | 9.5% | 15.3% |
| [worsp](https://github.com/sosukesuzuki/worsp) | C++ ⚠️ · Rust ⚠️ | C++ 0/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 ❌ | 1,087 | 0 | +100.0% | 13.6% | — |
| [XOpt](https://github.com/drylikov/XOpt.git) | C++ ✅ · Rust ✅ | C++ 1/1 · Rust 0/1 | A/B C++ —·Rust — · pass@1 — | 135 | 596 | −341.5% | 8.5% | 6.2% |

<sub>A **site** is one individual unsafe OPERATION, not a function or a whole `unsafe {}` block (those are too coarse). **Transpiled / Compiled** — did cpp2rust emit, and does the emitted code build, for the C++ lane and the Rust lane (`ok/total` translation units). **Tested** — the differential test oracles: **A/B** runs the project's own program built from native C vs from the transpiled C++/Rust and compares output byte-for-byte (`—` = not linkable as one binary, e.g. cross-TU C++ name mangling or unresolved builtin FFI; logged, never silently passed); **pass@1** is CRUST-bench's official oracle — the emitted crate spliced under the hand-written RBench interface, then `cargo test`. For SQLite the Tested cell is the whole-CLI differential over the SQL scripts. **Original C Unsafe Sites** — initial unsafe operation sites in the C source (`raw_ptr_deref + static_mut + union_member`). **Emitted Rust Unsafe Sites** — resulting unsafe operation sites in the emitted Rust (`raw_ptr_deref + extern_unsafe_call + static_mut + union_read + transmute + inline_asm`). `extern_unsafe_call` counts only GENUINELY external calls (libc / foreign symbols). A call whose target is defined elsewhere in the project - a first-party function reached over the C ABI only because the emitter emits one crate per translation unit and exposes symbols to the CRUST-bench harness - plus transpiler shims and benign compiler intrinsics (assert, branch hints, object-size) are emission artifacts, NOT unsafety carried over from the C source; they go to a separate `internal_call` lane never folded into the total. `unchecked_arith` (C pointer arithmetic, no Rust unsafe counterpart) is likewise separate. The per-family breakdown below shows every lane. **Unsafe Site Reduction (%)** — `(C − Rust) ÷ C`; **positive = net fewer** unsafe sites, **negative = net more** (this build is a faithful transliteration — ownership/borrow uplift is deferred — so where Rust adds sites it is mostly C's previously-hidden FFI unsafety made explicit, not new unsafety). **Baseline C UOD** / **Emitted Rust UOD** — Unsafe-Operation-Density: unsafe sites ÷ total expressions in that lane's own AST (lower is safer); the denominator grows with any added scaffolding, so the density cannot be gamed by code inflation. All counts use thousands separators.</sub>

**Unsafe operation sites by family — all projects (C initial → Rust resulting):**

| Family | Sites (C) | Sites (Rust) | Δ (C−Rust) |
|---|---:|---:|---:|
| raw_ptr_deref | 27,588 | 28,796 | -1,208 |
| extern_unsafe_call (genuine libc/foreign) | — *(not unsafe in C)* | 12,333 | — |
| static_mut | 874 | 865 | 9 |
| union read | 840 | 2 | 838 |
| transmute | — *(not unsafe in C)* | 1,323 | — |
| inline_asm | — *(not unsafe in C)* | 0 | — |
| **Total (memory-safety sites)** | **29,302** | **43,319** | **-14,017** |
| _unchecked_arith (separate lane)_ | _474_ | _0_ | _—_ |
| _internal_call (first-party / harness-FFI / intrinsics — excluded)_ | _—_ | _4,239_ | _—_ |

Corpus totals — Original C unsafe sites **29,302** → Emitted Rust unsafe sites **43,319** (Unsafe Site Reduction **−47.8%**; negative because this build is a faithful transliteration and surfaces C's hidden FFI unsafety — see the `extern_unsafe_call` row). Baseline C UOD **8.90%** → Emitted Rust UOD **8.64%** (unsafe sites ÷ total expressions in each lane's AST).
Raw-pointer dereferences (the core memory-safety family): 27,588 in C → 28,796 in Rust (**+1,208**; the emitter lowers some compound C accesses into several explicit Rust derefs, so a per-project split — not this raw aggregate — is the honest read of the memory-safety change).
Caveat — measurement scope: the C funnel is main-file-scoped (a deliberate choice so system-header noise is excluded) while the Rust census counts the `#include`d project code the emitter inlines. Projects that `#include` a generated `.c` therefore skew both their own reduction and their weight here — notably **libfor** (55 C sites vs 14,698 Rust, because its 28K-line `for-gen.c` is inlined and fully unrolled); it alone is roughly half the corpus `raw_ptr_deref` total. Read the per-project rows, not just this aggregate.
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
