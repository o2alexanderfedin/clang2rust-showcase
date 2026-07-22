#!/usr/bin/env bash
#
# run_crust_bench.sh — score clang2rust against ALL 100 CRUST-bench projects,
# running each through the SAME 6-stage differential process as SQLite plus
# the two test oracles and the per-operation unsafe-SITE census.
#
# CRUST-bench (https://github.com/anirudhkhatry/CRUST-bench) is a published
# benchmark of 100 C repositories, each paired with a hand-written safe-Rust
# interface and test suite (see benchmarks/CRUST-bench.md for the methodology).
#
# This script is now a thin ORCHESTRATOR: it fetches the dataset into an
# external, git-ignored cache, then fans `run_crust_project.sh` out over every
# project at moderate parallelism, and finally aggregates a summary + renders
# the published report. All the real per-project work (compile_commands
# synthesis, the 6 stages, A/B, pass@1, site census) lives in the
# project-agnostic driver `run_crust_project.sh` (DESIGN.md D1).
#
# Usage:
#   run_crust_bench.sh [--transpiler <path>] [--census <path>] [--cache <dir>]
#                      [--jobs N] [--only "p1 p2 …"] [--dry-run]
#
#   --transpiler <path>  cpp2rust binary. Default: the worktree/main build.
#   --census <path>      unsafe_census binary (extended, operation-level).
#   --cache <dir>        External, git-ignored dataset+results cache.
#                        Default: $XDG_CACHE_HOME/clang2rust/crust-bench.
#   --jobs N             Parallel projects (default 4 — MODERATE, leaves CPU
#                        headroom for other work; do NOT raise blindly).
#   --only "…"           Space-separated project subset (pilot runs).
#   --dry-run            Print the plan and exit.
#
# Requirements: the two binaries (built), cargo/rustc, clang++/clang (C++26 +
# libc++), curl+unzip (fetch), and `bear` for Makefile-only projects.
#
# Outputs (under the --cache dir, alongside the dataset):
#   results/<project>.tsv   Per-project honest funnel row (driver schema).
#   results/summary.tsv     Aggregate funnel across all projects.
#   results/REPORT.md       Rendered site-granular report.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRANSPILER="${TRANSPILER:-${SCRIPT_DIR}/../../cpp-to-rust/cpp/build/bin/cpp2rust}"
UNSAFE_CENSUS_BIN="${UNSAFE_CENSUS_BIN:-${SCRIPT_DIR}/../../cpp-to-rust/rust/target/release/unsafe_census}"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/clang2rust/crust-bench"
JOBS=4
ONLY=""
DRY_RUN=0

CRUST_BENCH_REPO="https://github.com/anirudhkhatry/CRUST-bench"
CRUST_BENCH_DATASET_ZIP_PATH="datasets"

usage() { sed -n '2,/^set -uo pipefail/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' | sed '$d'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --transpiler) TRANSPILER="$2"; shift 2 ;;
    --census) UNSAFE_CENSUS_BIN="$2"; shift 2 ;;
    --cache) CACHE_DIR="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unrecognized argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

DATASET_DIR="${CACHE_DIR}/dataset"
CBENCH_DIR="${DATASET_DIR}/CBench"
RBENCH_DIR="${DATASET_DIR}/RBench"
RESULTS_DIR="${CACHE_DIR}/results"
SUMMARY_TSV="${RESULTS_DIR}/summary.tsv"

log() { printf '[run_crust_bench] %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# Fetch the dataset into the external cache (never into this repo — GPL-3.0).
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
  rm -rf "$extract_dir"; mkdir -p "$extract_dir"
  unzip -q "$archive" -d "$extract_dir"
  local repo_root
  repo_root="$(find "$extract_dir" -maxdepth 1 -mindepth 1 -type d | head -n1)"
  local dataset_zip
  dataset_zip="$(find "${repo_root}/${CRUST_BENCH_DATASET_ZIP_PATH}" -iname '*.zip' 2>/dev/null | head -n1)"
  mkdir -p "$DATASET_DIR"
  if [ -n "$dataset_zip" ]; then
    unzip -q "$dataset_zip" -d "$DATASET_DIR"
  else
    log "warning: no dataset zip found — copying repo dataset dirs directly"
    cp -R "${repo_root}/CBench" "$CBENCH_DIR" 2>/dev/null || true
    cp -R "${repo_root}/RBench" "$RBENCH_DIR" 2>/dev/null || true
  fi
  rm -rf "$extract_dir" "$archive"
}

# ---------------------------------------------------------------------------
# Aggregate the per-project driver rows into an honest funnel (DESIGN.md D5).
# ---------------------------------------------------------------------------
write_summary() {
  python3 - "$RESULTS_DIR" > "$SUMMARY_TSV" <<'PY'
import os, sys
results = sys.argv[1]
rows = []
for f in sorted(os.listdir(results)):
    if not f.endswith(".tsv") or f == "summary.tsv":
        continue
    d = {}
    for part in open(os.path.join(results, f)).read().strip().split("\t"):
        if "=" in part:
            k, v = part.split("=", 1); d[k] = v
    rows.append(d)

def gi(d, k):
    try: return int(d.get(k, "0"))
    except ValueError: return 0
def ratio_full(d, k):
    v = d.get(k, "0/0")
    try: a, b = v.split("/"); return int(b) > 0 and a == b
    except Exception: return False

N = len(rows)
def count(pred): return sum(1 for r in rows if pred(r))

fields = ["transpiled_cpp","cpp_crates","compiled_cpp","transpiled_rust","rust_crates",
          "compiled_rust","ab_cpp","ab_rust","pass1","c_sites","r_sites","note"]
print("project\t" + "\t".join(fields))
for r in rows:
    print(r.get("project","?") + "\t" + "\t".join(r.get(k,"") for k in fields))

fam_c = ["c_raw_ptr_deref","c_static_mut","c_union_member","c_unchecked_arith"]
fam_r = ["r_raw_ptr_deref","r_extern_unsafe_call","r_static_mut","r_union_read",
         "r_transmute","r_inline_asm","r_unchecked_arith","r_unsafe_blocks"]
tot = lambda k: sum(gi(r, k) for r in rows)

print()
print(f"# aggregate over {N} projects")
print(f"# transpiled_cpp=yes:   {count(lambda r: r.get('transpiled_cpp')=='yes')}/{N}")
print(f"# transpiled_rust=yes:  {count(lambda r: r.get('transpiled_rust')=='yes')}/{N}")
print(f"# compiled_cpp=full:    {count(lambda r: ratio_full(r,'compiled_cpp'))}/{N}")
print(f"# compiled_rust=full:   {count(lambda r: ratio_full(r,'compiled_rust'))}/{N}")
print(f"# ab_cpp=pass:          {count(lambda r: r.get('ab_cpp')=='pass')}/{N}")
print(f"# ab_rust=pass:         {count(lambda r: r.get('ab_rust')=='pass')}/{N}")
print(f"# pass1=pass:           {count(lambda r: r.get('pass1')=='pass')}/{N}")
print(f"# C  unsafe sites total: {tot('c_sites')}   " + " ".join(f"{k}={tot(k)}" for k in fam_c))
print(f"# Rust unsafe sites total: {tot('r_sites')}  " + " ".join(f"{k}={tot(k)}" for k in fam_r))
print(f"# Rust total exprs (UOD denom): {tot('rust_exprs')}")
PY
  log "summary written to $SUMMARY_TSV"
  # Render the published site-granular report (SQLite consumes its own site
  # TSV if present; otherwise renders pending-regen — see generate_report.py).
  if command -v python3 >/dev/null 2>&1; then
    python3 "${SCRIPT_DIR}/generate_report.py" "$RESULTS_DIR" "$CBENCH_DIR" \
      > "${RESULTS_DIR}/REPORT.md" 2>>"${RESULTS_DIR}/report.err" \
      && log "per-project report written to ${RESULTS_DIR}/REPORT.md"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  log "transpiler:  $TRANSPILER"
  log "census:      $UNSAFE_CENSUS_BIN"
  log "cache dir:   $CACHE_DIR"
  log "jobs:        $JOBS"

  if [ "$DRY_RUN" -eq 1 ]; then
    log "dry run — planned steps:"
    log "  1. fetch CRUST-bench (GPL-3.0) into $DATASET_DIR"
    log "  2. run_crust_project.sh over every project at -P${JOBS}"
    log "  3. aggregate results/summary.tsv and render results/REPORT.md"
    exit 0
  fi

  [ -x "$TRANSPILER" ] || { echo "error: transpiler not executable: $TRANSPILER" >&2; exit 1; }
  [ -x "$UNSAFE_CENSUS_BIN" ] || { echo "error: unsafe_census not executable: $UNSAFE_CENSUS_BIN" >&2; exit 1; }

  mkdir -p "$RESULTS_DIR"
  fetch_dataset
  [ -d "$CBENCH_DIR" ] || { echo "error: dataset fetch did not produce $CBENCH_DIR" >&2; exit 1; }

  # Project list (all, or the --only subset).
  local projects
  if [ -n "$ONLY" ]; then
    projects="$ONLY"
  else
    projects="$(cd "$CBENCH_DIR" && for d in */; do [ -d "$d" ] && printf '%s\n' "${d%/}"; done)"
  fi

  export TRANSPILER UNSAFE_CENSUS_BIN CACHE_DIR RESULTS_DIR
  log "scoring $(printf '%s\n' $projects | wc -l | tr -d ' ') projects at -P${JOBS}"
  printf '%s\n' $projects | xargs -P "$JOBS" -I {} bash "${SCRIPT_DIR}/run_crust_project.sh" {}

  write_summary
}

main "$@"
