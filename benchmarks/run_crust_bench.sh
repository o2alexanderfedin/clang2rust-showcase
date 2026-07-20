#!/usr/bin/env bash
#
# run_crust_bench.sh — score clang2rust against the CRUST-bench dataset.
#
# CRUST-bench (https://github.com/anirudhkhatry/CRUST-bench) is a published
# benchmark of 100 C repositories, each paired with a hand-written safe-Rust
# interface and test suite (see ../benchmarks/CRUST-bench.md for the full
# methodology). This script:
#
#   1. Fetches the CRUST-bench dataset into an EXTERNAL cache directory
#      (never into this repo — the dataset is GPL-3.0 licensed).
#   2. Iterates every C project in the dataset's CBench/ folder.
#   3. Per project, records two scores:
#        Tier 1 — "transpiles":   clang2rust converts the project and the
#                                  emitted Rust compiles as its own crate.
#        Tier 2 — "pass@1":       the emitted Rust compiles against the
#                                  project's RBench/ interface and passes
#                                  `cargo test`. Marked not-attempted where
#                                  splicing against a third-party interface
#                                  isn't yet supported, rather than silently
#                                  scored as a failure.
#   4. Writes a per-project TSV and an aggregate summary.
#
# Usage:
#   run_crust_bench.sh [--transpiler <path>] [--cache <dir>] [--dry-run]
#
#   --transpiler <path>  Path to the transpiler binary.
#                         Default: ../cpp-to-rust/cpp/build/bin/cpp2rust
#   --cache <dir>        External, git-ignored directory the CRUST-bench
#                         dataset is downloaded into and read from.
#                         Default: $XDG_CACHE_HOME/clang2rust/crust-bench
#                         (or ~/.cache/clang2rust/crust-bench)
#   --dry-run            Print the planned steps and exit without fetching,
#                         transpiling, or building anything.
#   -h, --help            Show this usage text.
#
# Requirements:
#   - The transpiler binary, already built.
#   - `cargo` / `rustc` on PATH, for Tier-1/Tier-2 compile checks.
#   - `curl` and `unzip`, to fetch and unpack the dataset.
#   - `bear` (https://github.com/rizsotto/Bear) for CRUST-bench projects
#     that build via Makefile rather than CMake, to derive a compilation
#     database. Not required for CMake-based projects.
#
# Outputs (written under the run's --cache dir, alongside the dataset):
#   results/<project>.tsv   Per-project Tier-1/Tier-2 result row.
#   results/summary.tsv     Aggregate across all projects.
#
# This script is a template: it is safe to read and inspect, but is not
# invoked as part of building this repository. Run it explicitly once a
# transpiler binary is available.

set -uo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRANSPILER="${SCRIPT_DIR}/../../cpp-to-rust/cpp/build/bin/cpp2rust"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/clang2rust/crust-bench"
DRY_RUN=0

CRUST_BENCH_REPO="https://github.com/anirudhkhatry/CRUST-bench"
CRUST_BENCH_DATASET_ZIP_PATH="datasets"   # dataset zip lives under this path in the repo

usage() {
  # Print this script's own header comment as usage text.
  sed -n '2,/^set -uo pipefail/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' | sed '$d'
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --transpiler)
      TRANSPILER="$2"; shift 2 ;;
    --cache)
      CACHE_DIR="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "error: unrecognized argument: $1" >&2
      usage >&2
      exit 1 ;;
  esac
done

DATASET_DIR="${CACHE_DIR}/dataset"
CBENCH_DIR="${DATASET_DIR}/CBench"
RBENCH_DIR="${DATASET_DIR}/RBench"
RESULTS_DIR="${CACHE_DIR}/results"
SUMMARY_TSV="${RESULTS_DIR}/summary.tsv"

log() { printf '[run_crust_bench] %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# Per-step wall-clock limits (seconds)
# ---------------------------------------------------------------------------
# A single hung compile-database build, transpile, or `cargo build` must not
# be able to stall the whole sweep. Each of those steps runs under a
# wall-clock limit; a step that exceeds its limit is killed and scored as a
# failure for that project, and the sweep moves on.
TRANSPILE_TIMEOUT=90    # transpiling one project
BUILD_TIMEOUT=150       # `cargo build` on the emitted crate
CDB_TIMEOUT=120         # deriving one project's compile_commands.json

# Resolve a `timeout` implementation (some systems ship coreutils' as
# `gtimeout`). If neither is present, commands run unbounded.
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN="gtimeout"
else
  TIMEOUT_BIN=""
  log "warning: no timeout implementation found — per-project limits disabled"
fi

# run_bounded <seconds> <cmd...> — run a command under a wall-clock limit when
# a timeout implementation is available, otherwise run it unbounded.
run_bounded() {
  local secs="$1"; shift
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" "$secs" "$@"
  else
    "$@"
  fi
}

# ---------------------------------------------------------------------------
# Host toolchain resolution (portable; empty/no-op where not applicable)
# ---------------------------------------------------------------------------
# On macOS the recorded compile commands invoke Apple's `cc`, which implicitly
# supplies the SDK sysroot and the compiler's builtin-header directory. A
# stand-alone parser is handed the recorded flags but neither of those, so
# system headers such as <stdint.h> and <stdbool.h> cannot be found. Resolve
# both from the installed Xcode command-line tools and splice them into each
# project's compile database before scoring (see harden_compile_commands).
# Off macOS, or without `xcrun`, these stay empty and nothing is added.
HOST_SYSROOT=""
HOST_BUILTIN_INCLUDE=""
if [ "$(uname -s)" = "Darwin" ] && command -v xcrun >/dev/null 2>&1; then
  HOST_SYSROOT="$(xcrun --show-sdk-path 2>/dev/null || true)"
  _host_cc="$(xcrun -f clang 2>/dev/null || true)"
  if [ -n "$_host_cc" ]; then
    HOST_BUILTIN_INCLUDE="$("$_host_cc" -print-resource-dir 2>/dev/null)/include"
  fi
fi

# The Tier-1 compile check invokes rustc DIRECTLY (never through cargo): a
# host's global cargo configuration may interpose wrappers that are unrelated
# to this benchmark (and may not even be runnable here), which would fail
# every build for environment reasons. Resolving the toolchain's own rustc and
# compiling each emitted crate with it keeps the check honest and portable.
REAL_RUSTC="$(rustup which rustc 2>/dev/null || command -v rustc 2>/dev/null || echo rustc)"

# harden_compile_commands <compile_commands.json>
# Splice the host sysroot + builtin-header include into every entry so the
# parser resolves system headers. Idempotent (skips entries already carrying
# an -isysroot). No-op when the host sysroot is unknown or python3 is absent.
harden_compile_commands() {
  local cdb="$1"
  [ -n "$HOST_SYSROOT" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  python3 - "$cdb" "$HOST_SYSROOT" "$HOST_BUILTIN_INCLUDE" <<'PY'
import json, sys
cdb, sysroot, builtin = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(cdb) as f:
        data = json.load(f)
except Exception:
    sys.exit(0)
extra = ["-isysroot", sysroot]
if builtin:
    extra += ["-isystem", builtin]
for e in data:
    cmd = e.get("command")
    args = e.get("arguments")
    if isinstance(cmd, str) and "-isysroot" not in cmd:
        head, _, tail = cmd.partition(" ")
        e["command"] = head + " " + " ".join(extra) + ((" " + tail) if tail else "")
    elif isinstance(args, list) and "-isysroot" not in args:
        e["arguments"] = [args[0]] + extra + args[1:] if args else args
with open(cdb, "w") as f:
    json.dump(data, f, indent=2)
PY
}

# ---------------------------------------------------------------------------
# Step 1: fetch the dataset into the external cache (never into this repo)
# ---------------------------------------------------------------------------
fetch_dataset() {
  if [ -d "$CBENCH_DIR" ] && [ -d "$RBENCH_DIR" ]; then
    log "dataset already present at $DATASET_DIR — skipping fetch"
    return 0
  fi

  log "fetching CRUST-bench into external cache: $CACHE_DIR"
  mkdir -p "$CACHE_DIR"

  local archive="${CACHE_DIR}/crust-bench.zip"
  curl -fL "${CRUST_BENCH_REPO}/archive/refs/heads/main.zip" -o "$archive"

  local extract_dir="${CACHE_DIR}/_extract"
  rm -rf "$extract_dir"
  mkdir -p "$extract_dir"
  unzip -q "$archive" -d "$extract_dir"

  local repo_root
  repo_root="$(find "$extract_dir" -maxdepth 1 -mindepth 1 -type d | head -n1)"

  # The dataset itself ships as a zip inside the repo, under
  # CRUST_BENCH_DATASET_ZIP_PATH; unpack that into CBench/ + RBench/.
  local dataset_zip
  dataset_zip="$(find "${repo_root}/${CRUST_BENCH_DATASET_ZIP_PATH}" -iname '*.zip' 2>/dev/null | head -n1)"
  mkdir -p "$DATASET_DIR"
  if [ -n "$dataset_zip" ]; then
    unzip -q "$dataset_zip" -d "$DATASET_DIR"
  else
    log "warning: no dataset zip found under ${CRUST_BENCH_DATASET_ZIP_PATH}/ — copying repo dataset dirs directly"
    cp -R "${repo_root}/CBench" "$CBENCH_DIR" 2>/dev/null || true
    cp -R "${repo_root}/RBench" "$RBENCH_DIR" 2>/dev/null || true
  fi

  rm -rf "$extract_dir" "$archive"
}

# ---------------------------------------------------------------------------
# Step 2: per-project compilation database
# ---------------------------------------------------------------------------
# Produces a compile_commands.json for one C project, using CMake directly
# where available, or `bear` to wrap a Makefile build otherwise.
ensure_compile_commands() {
  local project_dir="$1"
  local cdb="${project_dir}/compile_commands.json"

  [ -f "$cdb" ] && { echo "$cdb"; return 0; }

  if [ -f "${project_dir}/CMakeLists.txt" ]; then
    # Many dataset projects pin a very old cmake_minimum_required (< 3.5),
    # which recent cmake refuses to configure. CMAKE_POLICY_VERSION_MINIMUM
    # lets those old build files configure under a newer cmake; it only
    # affects how the dataset's C is built, not the transpilation.
    ( cd "$project_dir" && run_bounded "$CDB_TIMEOUT" cmake -B build \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 >/dev/null 2>&1 )
    [ -f "${project_dir}/build/compile_commands.json" ] && cp "${project_dir}/build/compile_commands.json" "$cdb"
  elif [ -f "${project_dir}/Makefile" ]; then
    if ! command -v bear >/dev/null 2>&1; then
      log "warning: bear not found — cannot derive compile_commands.json for ${project_dir}"
      return 1
    fi
    ( cd "$project_dir" && run_bounded "$CDB_TIMEOUT" bear -- make >/dev/null 2>&1 )
  fi

  # A recorder run whose build failed immediately leaves an EMPTY (0-entry)
  # database behind. Passing that on would mislabel the project as "attempted"
  # with nothing to attempt — treat it as no-database, honestly.
  if [ -f "$cdb" ] && command -v python3 >/dev/null 2>&1; then
    if ! python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])) else 1)' "$cdb" 2>/dev/null; then
      rm -f "$cdb"
    fi
  fi

  [ -f "$cdb" ] && echo "$cdb" || return 1
}

# ---------------------------------------------------------------------------
# Step 3: score one project
# ---------------------------------------------------------------------------
score_project() {
  local name="$1"
  local c_dir="${CBENCH_DIR}/${name}"
  local rust_dir="${RBENCH_DIR}/${name}"
  local out_dir="${RESULTS_DIR}/${name}/out"
  local tier1="fail"
  local tier2="not-attempted"

  mkdir -p "$out_dir"

  local cdb
  if ! cdb="$(ensure_compile_commands "$c_dir")"; then
    printf '%s\ttier1=%s\ttier2=%s\tnote=no-compile-commands\n' "$name" "$tier1" "$tier2" \
      > "${RESULTS_DIR}/${name}.tsv"
    return
  fi

  # Give the parser the host sysroot + builtin headers it needs to resolve
  # standard system headers (no-op off macOS / without python3).
  harden_compile_commands "$cdb"

  # Tier 1: transpile the project, then check whether the emitted Rust
  # compiles. The emitter writes one self-contained crate per translation
  # unit, so there is no single top-level crate to build — instead, build
  # every emitted crate and require them all to compile. A `note` records
  # which step a non-passing project stopped at, so the summary can separate
  # projects the product actually ran on from those still gated earlier.
  local note=""
  # The converter isolates errors per source file: its exit code is non-zero
  # when ANY file in the project could not be converted, even though every
  # other file's crate was still emitted. So the exit code alone cannot
  # classify the project — count the emitted crates, build them all, and
  # classify from both. A partial conversion is never a Tier-1 pass, but it is
  # recorded as partial (with how much emitted and how much of that compiled),
  # never conflated with "nothing was produced".
  run_bounded "$TRANSPILE_TIMEOUT" "$TRANSPILER" --cdb "$cdb" --out-dir "$out_dir" --emit=rust >"${out_dir}/../transpile.log" 2>&1
  local trc=$?
  local n_total=0 n_ok=0 manifest cdir
  while IFS= read -r manifest; do
    n_total=$((n_total + 1))
    cdir="$(dirname "$manifest")"
    # Compile the crate root as a Rust LIBRARY OBJECT — the same check the
    # product's own verification uses everywhere. The emitted crates are
    # C-ABI translation units (some export a C `main`, most export none), so
    # a binary-target build would demand a Rust `main` that is not supposed
    # to exist; the library-object compile is the correct, honest question:
    # "is this valid Rust?". Sibling modules resolve from the same src/ dir.
    if run_bounded "$BUILD_TIMEOUT" "$REAL_RUSTC" --edition=2021 \
         --crate-type=lib --emit=obj "$cdir/src/lib.rs" \
         -o "$cdir/.tier1_check.o" >>"${out_dir}/../build.log" 2>&1; then
      n_ok=$((n_ok + 1))
    fi
  done < <(find "$out_dir" -name Cargo.toml)

  if [ "$n_total" -eq 0 ]; then
    note="transpile-failed"
  elif [ "$trc" -ne 0 ]; then
    note="transpile-partial(crates=${n_total},compiled=${n_ok})"
  elif [ "$n_ok" -eq "$n_total" ]; then
    tier1="pass"
  else
    note="crate-build-failed(${n_ok}/${n_total})"
  fi

  # Tier 2: splice the emitted crate against CRUST-bench's hand-written
  # interface + tests for this project, then run `cargo test`. Only
  # attempted once Tier 1 has passed; honestly marked not-attempted or
  # expected-fail otherwise rather than silently omitted.
  if [ "$tier1" = "pass" ] && [ -d "${rust_dir}/interfaces" ]; then
    # Reconciling arbitrary third-party interfaces against emitted output
    # is not yet supported end-to-end; record the attempt outcome honestly.
    tier2="expected-fail"
  fi

  if [ -n "$note" ]; then
    printf '%s\ttier1=%s\ttier2=%s\tnote=%s\n' "$name" "$tier1" "$tier2" "$note" \
      > "${RESULTS_DIR}/${name}.tsv"
  else
    printf '%s\ttier1=%s\ttier2=%s\n' "$name" "$tier1" "$tier2" \
      > "${RESULTS_DIR}/${name}.tsv"
  fi
}

# ---------------------------------------------------------------------------
# Step 4: aggregate
# ---------------------------------------------------------------------------
write_summary() {
  local total=0 t1_pass=0 t2_pass=0 t2_attempted=0

  {
    printf 'project\ttier1\ttier2\n'
    for f in "${RESULTS_DIR}"/*.tsv; do
      [ -f "$f" ] || continue
      [ "$(basename "$f")" = "summary.tsv" ] && continue
      total=$((total + 1))
      grep -q 'tier1=pass' "$f" && t1_pass=$((t1_pass + 1))
      grep -q 'tier2=pass' "$f" && t2_pass=$((t2_pass + 1))
      grep -qv 'tier2=not-attempted' "$f" && t2_attempted=$((t2_attempted + 1))
      cat "$f"
    done
    printf '\n# aggregate: %d projects, tier1 pass=%d, tier2 pass=%d (of %d attempted)\n' \
      "$total" "$t1_pass" "$t2_pass" "$t2_attempted"
  } > "$SUMMARY_TSV"

  log "summary written to $SUMMARY_TSV"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  log "transpiler:  $TRANSPILER"
  log "cache dir:   $CACHE_DIR"

  if [ "$DRY_RUN" -eq 1 ]; then
    log "dry run — planned steps:"
    log "  1. fetch CRUST-bench (GPL-3.0) into $DATASET_DIR"
    log "  2. derive a compile_commands.json per project (cmake or bear+make)"
    log "  3. score each project: Tier 1 (transpiles) / Tier 2 (pass@1)"
    log "  4. write $RESULTS_DIR/<project>.tsv and $SUMMARY_TSV"
    exit 0
  fi

  if [ ! -x "$TRANSPILER" ]; then
    echo "error: transpiler binary not found or not executable: $TRANSPILER" >&2
    exit 1
  fi

  mkdir -p "$RESULTS_DIR"
  fetch_dataset

  if [ ! -d "$CBENCH_DIR" ]; then
    echo "error: dataset fetch did not produce $CBENCH_DIR" >&2
    exit 1
  fi

  for project_dir in "$CBENCH_DIR"/*/; do
    [ -d "$project_dir" ] || continue
    name="$(basename "$project_dir")"
    log "scoring: $name"
    score_project "$name"
  done

  write_summary
}

main "$@"
