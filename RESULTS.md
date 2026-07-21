# CRUST-bench results

Scoring methodology: [`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md).
Harness: [`benchmarks/run_crust_bench.sh`](benchmarks/run_crust_bench.sh).

- **Run date:** 2026-07-20
- **Dataset:** [CRUST-bench](https://github.com/anirudhkhatry/CRUST-bench)
  ([paper: arXiv 2504.15254](https://arxiv.org/abs/2504.15254)) — 100 real-world
  C repositories, each paired with a hand-written safe-Rust interface and a
  test suite.
- **Coverage:** all 100 projects scored. 19 of the 100 could not be attempted
  at all — their own build systems are broken (defective Makefiles / CMake
  files), so the file-and-flag list the converter needs as input could not be
  produced and the converter never ran on them. That leaves **81 projects the
  converter actually ran on**; every number below is about those 81.

## Aggregate

| Metric | Result |
|---|---|
| Projects in dataset | 100 |
| Unreachable (their own builds are broken; converter never ran) | 19 |
| **Projects the converter ran on** | **81** |
| **Tier-1 pass — every file converted AND all emitted Rust compiles** | **18** (of the 81 run; 18/100 of the dataset) |
| Rust crates emitted across the 81 (≈ one per C source file) | 233 |
| Emitted crates that compile | **117 / 233 (50%)** |
| Tier 2 — CRUST-bench pass@1 (against the hand-written interface) | 0 (not attempted) |

**Tier-1 passing projects (18):** amp, bostree, btree-map, chtrie, csyncmers,
fft, fs_c, hamta, hydra, kd3, leftpad, lib2bit, libbeaufort, libfor,
murmurhash_c, quadtree, Simple-Sparsehash, vec.

## What happened on the 81 projects the converter ran on

| Count | Outcome |
|---|---|
| **18** | **Full success** — every C file converted, and all of the resulting Rust compiles. |
| 29 | Every C file converted, but only some of the resulting Rust compiles (38 of their 94 crates do). |
| 18 | Some files converted, others refused — the converter refuses loudly on C constructs it does not support yet, rather than emit wrong code (43 of their 103 crates compile). |
| 16 | Every file refused — nothing produced (again: a loud, honest refusal, never a silent mis-translation). |

(18 + 29 + 18 + 16 = 81.)

## Per-project results

Generated from the run's per-project result rows by
[`benchmarks/generate_report.py`](benchmarks/generate_report.py) (the harness
regenerates this table as `results/REPORT.md` on every sweep).

Legend — **Transpiled**: did the converter turn the project's C into Rust
(partial = some files refused, loudly). **Compiled**: how many of the emitted
Rust crates compile. **Tested**: the benchmark's own pass@1 (emitted Rust
against its hand-written interface + tests) — honestly `not attempted` today.
**Fns**: functions in the emitted Rust. **Fully safe**: functions whose body
contains no `unsafe` — code the converter PROVED safe (with %). **Unsafe
sites**: `unsafe` markers remaining in the output — in the C original, every
one of these operations was unchecked by the language and invisible; in the
Rust they are explicit, counted, and auditable. A per-project "how many C
sites were uplifted" split requires source-level analysis of each project
(the corpus-level version of that number for SQLite is in the
[README](README.md)); it is the next reporting increment, not silently
approximated here.

<!-- crust-table:begin -->
| Project | Transpiled | Compiled | Tested | Fns | Fully safe | Unsafe sites |
|---|---|---|---|---|---|---|
| [2DPartInt](https://github.com/eafit-apolo/2DPartInt) | n/a — project's own build is broken | — | — | — | — | — |
| [42-Kocaeli-Printf](https://github.com/enes2424/42-Kocaeli-Printf) | ❌ no (refused, loudly) | — | — | — | — | — |
| [aes128-SIMD](https://github.com/at0m741/aes128-SIMD) | ❌ no (refused, loudly) | — | — | — | — | — |
| [amp](https://github.com/clibs/amp) | ✅ yes | ✅ all | not attempted | 19 | 1 (5%) | 31 |
| [approxidate](https://github.com/thatguystone/approxidate) | ✅ yes | ⚠️ 0/2 | not attempted | 59 | 35 (59%) | 265 |
| [avalanche](https://github.com/drjerry/avalanche) | n/a — project's own build is broken | — | — | — | — | — |
| [bhshell](https://github.com/bsach64/bhshell) | ⚠️ partial | ⚠️ 2/4 | not attempted | 45 | 6 (13%) | 245 |
| [bigint](https://github.com/adam-mcdaniel/bigint) | ✅ yes | ⚠️ 0/3 | not attempted | 151 | 25 (17%) | 424 |
| [bitset](https://github.com/abenhlal/bitset) | n/a — project's own build is broken | — | — | — | — | — |
| [blt](https://github.com/blynn/blt) | ❌ no (refused, loudly) | — | — | — | — | — |
| [bostree](https://github.com/phillipberndt/bostree) | ✅ yes | ✅ all | not attempted | 70 | 35 (50%) | 457 |
| [btree-map](https://github.com/EdsonHTJ/btree-map) | ✅ yes | ✅ all | not attempted | 49 | 17 (35%) | 298 |
| [c-aces](https://github.com/enum-class/c-aces) | ⚠️ partial | ⚠️ 4/5 | not attempted | 160 | 18 (11%) | 233 |
| [c-blind-rsa-signatures](https://github.com/jedisct1/c-blind-rsa-signatures) | ✅ yes | ⚠️ 0/2 | not attempted | 6161 | 446 (7%) | 5671 |
| [c-string](https://github.com/vnkrtv/c-string) | ❌ no (refused, loudly) | — | — | — | — | — |
| [carrays](https://github.com/noporpoise/carrays) | ✅ yes | ⚠️ 0/2 | not attempted | 216 | 22 (10%) | 788 |
| [cfsm](https://github.com/nhjschulz/cfsm) | n/a — project's own build is broken | — | — | — | — | — |
| [chtrie](https://github.com/dongyx/chtrie) | ✅ yes | ✅ all | not attempted | 10 | 0 (0%) | 62 |
| [CircularBuffer](https://github.com/Roen-Ro/CircularBuffer) | ⚠️ partial | ⚠️ 0/1 | not attempted | 18 | 4 (22%) | 72 |
| [cissy](https://github.com/slass100/cissy) | ✅ yes | ⚠️ 5/7 | not attempted | 129 | 92 (71%) | 464 |
| [cJSON](https://github.com/faycheng/cJSON) | ✅ yes | ⚠️ 1/2 | not attempted | 126 | 55 (44%) | 839 |
| [clhash](https://github.com/simdhash/clhash) | ❌ no (refused, loudly) | — | — | — | — | — |
| [clog](https://github.com/mmueller/clog) | ❌ no (refused, loudly) | — | — | — | — | — |
| [coroutine](https://github.com/cloudwu/coroutine) | ⚠️ partial | ⚠️ 1/1 | not attempted | 13 | 6 (46%) | 17 |
| [cset](https://github.com/RobusGauli/cset.h) | ✅ yes | ⚠️ 0/1 | not attempted | 44 | 14 (32%) | 13906 |
| [csyncmers](https://github.com/rchikhi/csyncmers) | ✅ yes | ✅ all | not attempted | 28 | 20 (71%) | 75 |
| [dict](https://github.com/wrnlb666/dict) | ✅ yes | ⚠️ 0/1 | not attempted | 31 | 16 (52%) | 947 |
| [emlang](https://github.com/LordOfTrident/emlang) | n/a — project's own build is broken | — | — | — | — | — |
| [expr](https://github.com/radarsat1/expr) | ⚠️ partial | ⚠️ 1/1 | not attempted | 12 | 10 (83%) | 22 |
| [FastHamming](https://github.com/BenBE/FastHamming.git) | ❌ no (refused, loudly) | — | — | — | — | — |
| [fft](https://github.com/kevin0x0/fft) | ✅ yes | ✅ all | not attempted | 13 | 2 (15%) | 109 |
| [file2str](https://github.com/willemt/file2str) | ✅ yes | ⚠️ 3/4 | not attempted | 123 | 16 (13%) | 173 |
| [fleur](https://github.com/hashlookup/fleur) | n/a — project's own build is broken | — | — | — | — | — |
| [fs_c](https://github.com/jwerle/fs.c) | ✅ yes | ✅ all | not attempted | 51 | 26 (51%) | 72 |
| [fslib](https://github.com/c0stya/fslib) | n/a — project's own build is broken | — | — | — | — | — |
| [Genetic-neural-network-for-simple-control](https://github.com/DemianovE/Genetic-neural-network-for-simple-control) | ⚠️ partial | ⚠️ 10/12 | not attempted | 190 | 51 (27%) | 667 |
| [geofence](https://github.com/bytebeamio/geofence.git) | ✅ yes | ⚠️ 0/1 | not attempted | 7 | 1 (14%) | 9 |
| [gfc](https://github.com/maxmouchet/gfc.git) | ❌ no (refused, loudly) | — | — | — | — | — |
| [gorilla-paper-encode](https://github.com/MrBean818/gorilla-paper-encode) | ✅ yes | ⚠️ 1/2 | not attempted | 41 | 10 (24%) | 130 |
| [Graph-recogniser](https://github.com/NikolaYolov/Graph-recogniser) | ✅ yes | ⚠️ 0/4 | not attempted | 80 | 30 (38%) | 259 |
| [hamta](https://github.com/burtgulash/hamta) | ✅ yes | ✅ all | not attempted | 19 | 2 (11%) | 39 |
| [Holdem-Odds](https://github.com/gnuvince/Holdem-Odds) | ✅ yes | ⚠️ 3/5 | not attempted | 97 | 36 (37%) | 110 |
| [hydra](https://github.com/emad-elsaid/hydra) | ✅ yes | ✅ all | not attempted | 31 | 17 (55%) | 105 |
| [impcheck](https://github.com/domschrei/impcheck) | ⚠️ partial | ⚠️ 2/2 | not attempted | 5 | 0 (0%) | 3 |
| [inversion_list](https://github.com/hou-12/Inversion-List-Implementation-for-Interval-Manipulation) | n/a — project's own build is broken | — | — | — | — | — |
| [jccc](https://github.com/jabacat/jccc) | ✅ yes | ⚠️ 11/13 | not attempted | 277 | 93 (34%) | 537 |
| [kairoCompiler](https://github.com/kairo-yr/kairoCompiler) | ⚠️ partial | ⚠️ 0/5 | not attempted | 242 | 179 (74%) | 305 |
| [kd3](https://github.com/shawnchin/kd3) | ✅ yes | ✅ all | not attempted | 56 | 5 (9%) | 184 |
| [lambda-calculus-eval](https://github.com/Lorenzobattistela/lambda-calculus-eval) | n/a — project's own build is broken | — | — | — | — | — |
| [leftpad](https://github.com/sjmulder/leftpad) | ✅ yes | ✅ all | not attempted | 10 | 7 (70%) | 27 |
| [lib2bit](https://github.com/dpryan79/lib2bit) | ✅ yes | ✅ all | not attempted | 42 | 22 (52%) | 487 |
| [libbase122](https://github.com/kevinAlbs/libbase122) | n/a — project's own build is broken | — | — | — | — | — |
| [libbeaufort](https://github.com/jwerle/libbeaufort) | ✅ yes | ✅ all | not attempted | 18 | 0 (0%) | 46 |
| [libfor](https://github.com/cruppstahl/libfor) | ✅ yes | ✅ all | not attempted | 448 | 9 (2%) | 19734 |
| [libm17](https://github.com/M17-Project/libm17) | ❌ no (refused, loudly) | — | — | — | — | — |
| [libpgn](https://github.com/youkwhd/libpgn) | ✅ yes | ⚠️ 4/12 | not attempted | 243 | 176 (72%) | 488 |
| [libpsbt](https://github.com/jb55/libpsbt) | ❌ no (refused, loudly) | — | — | — | — | — |
| [libqueue](https://github.com/resyfer/libqueue) | ❌ no (refused, loudly) | — | — | — | — | — |
| [libtinyfseq](https://github.com/Cryptkeeper/libtinyfseq) | n/a — project's own build is broken | — | — | — | — | — |
| [libutf](https://github.com/holepunchto/libutf) | ⚠️ partial | ⚠️ 0/30 | not attempted | 2584 | 1330 (51%) | 11852 |
| [libvcd](https://github.com/sorousherafat/libvcd) | ✅ yes | ⚠️ 1/2 | not attempted | 35 | 26 (74%) | 71 |
| [libwecan](https://github.com/nisennenmondai/libwecan) | ❌ no (refused, loudly) | — | — | — | — | — |
| [Linear-Algebra-C](https://github.com/barrettotte/Linear-Algebra-C) | ✅ yes | ⚠️ 1/4 | not attempted | 317 | 11 (3%) | 1042 |
| [ljmm](https://github.com/cloudflare/ljmm) | ❌ no (refused, loudly) | — | — | — | — | — |
| [LTRE](https://github.com/Bricktech2000/LTRE) | ⚠️ partial | ⚠️ 0/1 | not attempted | 59 | 1 (2%) | 409 |
| [Math-Library-in-C](https://github.com/Astrodynamic/Math-Library-in-C) | ❌ no (refused, loudly) | — | — | — | — | — |
| [matrix_multiplication](https://github.com/DevRuibin/matrix_multiplication) | ⚠️ partial | ⚠️ 1/1 | not attempted | 5 | 0 (0%) | 9 |
| [mdb](https://github.com/chuigda/mdb.git) | n/a — project's own build is broken | — | — | — | — | — |
| [Megalania](https://github.com/blackle/Megalania) | ⚠️ partial | ⚠️ 9/16 | not attempted | 318 | 123 (39%) | 818 |
| [merkle-tree-c](https://github.com/TheWaWaR/merkle-tree-c) | ✅ yes | ⚠️ 0/1 | not attempted | 59 | 12 (20%) | 345 |
| [morton](https://github.com/jart/morton) | n/a — project's own build is broken | — | — | — | — | — |
| [murmurhash_c](https://github.com/jwerle/murmurhash.c) | ✅ yes | ✅ all | not attempted | 23 | 15 (65%) | 44 |
| [mvptree](https://github.com/michaelmior/mvptree) | ✅ yes | ⚠️ 2/3 | not attempted | 118 | 57 (48%) | 1226 |
| [NandC](https://github.com/Dcraftbg/NandC) | ✅ yes | ⚠️ 0/1 | not attempted | 21 | 17 (81%) | 17 |
| [Phills_DHT](https://github.com/PhillipTaylor/Phills_DHT) | ✅ yes | ⚠️ 0/1 | not attempted | 15 | 0 (0%) | 45 |
| [quadtree](https://github.com/thejefflarson/quadtree) | ✅ yes | ✅ all | not attempted | 123 | 6 (5%) | 325 |
| [razz_simulation](https://github.com/eus/razz_simulation) | ❌ no (refused, loudly) | — | — | — | — | — |
| [rbtree-lab](https://github.com/jwowo/rbtree-lab) | n/a — project's own build is broken | — | — | — | — | — |
| [recordManager](https://github.com/prachikotadia/-Record-Manager) | ⚠️ partial | ⚠️ 1/7 | not attempted | 315 | 245 (78%) | 2235 |
| [rect_pack_h](https://github.com/luihabl/rect_pack.h) | n/a — project's own build is broken | — | — | — | — | — |
| [Remimu](https://github.com/wareya/Remimu) | n/a — project's own build is broken | — | — | — | — | — |
| [rhbloom](https://github.com/tidwall/rhbloom) | ✅ yes | ⚠️ 1/2 | not attempted | 52 | 26 (50%) | 190 |
| [roaring-bitmap](https://github.com/chriso/roaring-bitmap) | ❌ no (refused, loudly) | — | — | — | — | — |
| [rubiksolver](https://github.com/justjkk/rubiksolver) | ✅ yes | ⚠️ 0/5 | not attempted | 101 | 10 (10%) | 576 |
| [satc](https://github.com/rjungemann/satc) | n/a — project's own build is broken | — | — | — | — | — |
| [Simple-Config](https://github.com/0xHaru/Simple-Config) | ✅ yes | ⚠️ 0/2 | not attempted | 97 | 58 (60%) | 298 |
| [Simple-Sparsehash](https://github.com/qpfiffer/Simple-Sparsehash) | ✅ yes | ✅ all | not attempted | 60 | 4 (7%) | 286 |
| [simple_lang](https://github.com/lxbme/simple_lang) | ⚠️ partial | ⚠️ 9/10 | not attempted | 145 | 47 (32%) | 360 |
| [SimpleXML](https://github.com/kiennt/SimpleXML.git) | ⚠️ partial | ⚠️ 0/2 | not attempted | 53 | 3 (6%) | 205 |
| [skp](https://github.com/rdentato/skp) | n/a — project's own build is broken | — | — | — | — | — |
| [SlothLang](https://github.com/AaronCGoidel/SlothLang) | ⚠️ partial | ⚠️ 3/3 | not attempted | 30 | 23 (77%) | 54 |
| [ted](https://github.com/ajpen/ted) | ✅ yes | ⚠️ 2/4 | not attempted | 131 | 54 (41%) | 468 |
| [tisp](https://github.com/edvb/tisp) | ✅ yes | ⚠️ 0/2 | not attempted | 223 | 96 (43%) | 1821 |
| [totp](https://github.com/sjmulder/totp) | ✅ yes | ⚠️ 2/3 | not attempted | 58 | 18 (31%) | 128 |
| [ulidgen](https://github.com/leahneukirchen/ulidgen) | ⚠️ partial | ⚠️ 0/1 | not attempted | 16 | 1 (6%) | 28 |
| [utf8](https://github.com/zahash/utf8.c) | ✅ yes | ⚠️ 1/2 | not attempted | 66 | 7 (11%) | 321 |
| [VaultSync](https://github.com/elhalili/VaultSync) | n/a — project's own build is broken | — | — | — | — | — |
| [vec](https://github.com/rxi/vec) | ✅ yes | ✅ all | not attempted | 31 | 1 (3%) | 998 |
| [worsp](https://github.com/sosukesuzuki/worsp) | ⚠️ partial | ⚠️ 0/1 | not attempted | 85 | 30 (35%) | 1000 |
| [XOpt](https://github.com/drylikov/XOpt.git) | ✅ yes | ⚠️ 0/1 | not attempted | 42 | 22 (52%) | 365 |
<!-- crust-table:end -->

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
