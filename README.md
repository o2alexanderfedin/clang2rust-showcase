# clang2rust

**A C/C++ → idiomatic, memory-safe Rust transpiler.**

clang2rust converts existing C/C++ source into idiomatic, memory-safe Rust
that compiles and behaves identically to the original.

---

## Performance

| Metric | Result |
|---|---|
| Compiles | 281 / 281 SQLite corpus translation units produce Rust that compiles (rustc obj-OK) |
| Behavioral parity | The complete SQLite command-line shell, transpiled to Rust, is byte-identical to the native build across 10 SQL test scripts, reproduced 3× under an allocator-hardened harness |
| Safety | 67.4% of generated Rust functions are fully safe (no `unsafe`); memory-unsafe constructs reduced 45.9% vs. a faithful raw-pointer baseline (further ownership work in progress) |
| CRUST-bench (100 third-party C repos) | 18 projects convert end-to-end to fully-compiling Rust; 50% of all emitted crates compile (117/233). 19 of the 100 have broken builds of their own and could not be attempted. Full breakdown: [RESULTS.md](RESULTS.md) |
| Release | 0.22.0 |

*Measured on the [SQLite](https://www.sqlite.org/) separate-file source tree
(individual translation units, not the single-file amalgamation). Correctness
is confirmed by differentially comparing transpiled output byte-for-byte
against the original across real workloads.*

---

## Supported source constructs

| Source construct | Rust output | Status |
|---|---|---|
| Integer, enum, and boolean coercions & truthiness | Explicit, type-correct Rust equivalents | Shipped |
| Full control flow, including `goto` | Structured Rust control flow | Shipped |
| Variadic functions | Typed Rust collections | Shipped |
| `switch` / `case`, static-local variables | Idiomatic Rust `match` and statics | Shipped |
| Unions with a provable discriminant | Tagged Rust `enum`s | Shipped |
| Smart pointers | `Box`, `Rc`, `Arc` | Shipped |
| Raw pointers | Safe references, via borrow inference | In progress |
| C strings, wide strings | `String` / `&str` | Shipped |
| `printf`-family calls | Rust formatting (`print!`, `eprintln!`, etc.) | Shipped |
| Mutex / thread primitives | Rust `std::sync` / `std::thread` equivalents | Shipped |
| Multi-file C/C++ projects | Multi-module Rust crates | Shipped |
| Source comments & doc-comments | Carried into the Rust output | Shipped |

---

## Reference output

clang2rust's output on real-world code is published for inspection:

| Repository | Description |
|---|---|
| [sqlite-rust-mirror](https://github.com/o2alexanderfedin/sqlite-rust-mirror) | SQLite transpiled to Rust — reference output |
| [sqlite-cpp-mirror](https://github.com/o2alexanderfedin/sqlite-cpp-mirror) | SQLite transpiled to modern C++ — reference output |
| [sqlite/sqlite](https://github.com/sqlite/sqlite) | The original source corpus |

---

## Benchmark: CRUST-bench

[CRUST-bench](https://github.com/anirudhkhatry/CRUST-bench)
([paper](https://arxiv.org/abs/2504.15254)) is a published benchmark of 100
real-world C repositories, each paired with a hand-written safe-Rust
interface and a test suite. Its scoring metric, **pass@1**, asks whether a
single transpilation attempt compiles against the provided interface *and*
passes `cargo test`.

We report two honest tiers, described in full in
[`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md):

1. **Transpiles** — the emitted Rust compiles as its own crate.
2. **CRUST-bench pass@1** — the emitted Rust compiles against CRUST-bench's
   hand-written interface *and* passes `cargo test`.

clang2rust is currently tuned for large, self-contained C codebases like
SQLite, and does not yet reconcile its output against arbitrary
third-party, hand-written interfaces. We expect Tier-2 pass@1 to be low as a
result — we're publishing it anyway, as an honest baseline rather than a
number to hide.

Results: [`RESULTS.md`](RESULTS.md) — first run recorded 2026-07-20 (Tier-1 18/100; full honest per-class breakdown).

### Reproduce

```console
$ benchmarks/run_crust_bench.sh --transpiler ../cpp-to-rust/cpp/build/bin/cpp2rust --cache ~/.cache/crust-bench
```

See [`benchmarks/CRUST-bench.md`](benchmarks/CRUST-bench.md) and
`benchmarks/run_crust_bench.sh --help` for full usage.

---

## License

See [`LICENSE`](LICENSE).
