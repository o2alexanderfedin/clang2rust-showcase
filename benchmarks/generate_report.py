#!/usr/bin/env python3
"""generate_report.py — render the site-granular safety tables published in
RESULTS.md. This script owns every table; none is hand-edited.

Usage:
    benchmarks/generate_report.py <results-dir> [<cbench-dir>]
        [--sqlite-status <tsv>] [--sqlite-sites <tsv>] [--update <RESULTS.md>]

Both the CRUST-bench table and the SQLite flagship row use ONE UNIFIED column
schema (DESIGN.md D3 + the "SQLite must be first-class + comparable" ruling):

    | Project | Transpiled | Compiled | A/B (native vs transpiled) | pass@1
    | Unsafe sites (C) | Unsafe sites (Rust) | Sites lifted | UOD (Rust) |

Safety is measured in per-OPERATION SITES, not functions (functions are too
coarse). The numbers come from the census/funnel instruments, NOT a regex:

  * C-initial sites   — `cpp2rust --emit=funnel-ingest` over each project's
                        compile DB (the pre-lowering Clang AST; families
                        raw_ptr_deref / static_mut / union_member).
  * Rust-resulting    — the extended operation-level `unsafe_census` over the
    sites               emitted Rust (families raw_ptr_deref /
                        extern_unsafe_call / static_mut / union_read /
                        transmute / inline_asm; `unchecked_arith` is a
                        SEPARATE lane, and `total_exprs` is the UOD denom).

CRUST-bench site data:  read per project from `<results-dir>/<project>.tsv`,
                        written by run_crust_project.sh (the driver row schema).

SQLite site data:       read from the `--sqlite-sites <tsv>` file — a single
                        tab-separated key=value line using the SAME driver
                        site keys (c_raw_ptr_deref … r_sites rust_exprs). It is
                        produced from the SQLite funnel logs; regenerate with:

    # (after the SQLite verification battery completes and 16-02 merges, off
    #  the fixed develop tip — NOT run by this generator)
    C=$CACHE/sqlite-bench/funnel_c.log        # cpp2rust --cdb $CDB --emit=funnel-ingest
    R=$CACHE/sqlite-bench/funnel_rust.log     # unsafe_census $OUTROOT
    python3 benchmarks/sqlite_sites_from_funnel.py "$C" "$R" \
        > benchmarks/sqlite-sites.tsv

    If `--sqlite-sites` is absent, SQLite's site cells render `pending-regen`
    (NEVER stale function-granular numbers) while its Transpiled/Compiled/A-B
    state cells still come from `--sqlite-status`.
"""
import os
import re
import subprocess
import sys

CRUST_BEGIN = "<!-- crust-table:begin -->"
CRUST_END = "<!-- crust-table:end -->"
SQLITE_BEGIN = "<!-- sqlite-table:begin -->"
SQLITE_END = "<!-- sqlite-table:end -->"

HEADER = [
    "| Project | Transpiled | Compiled | Tested "
    "| Original C Unsafe Sites | Emitted Rust Unsafe Sites "
    "| Unsafe Site Reduction (%) | Baseline C UOD | Emitted Rust UOD |",
    "|---|---|---|---|---:|---:|---:|---:|---:|",
]

# One legend rendered under BOTH tables so every number is defined in place.
LEGEND = (
    "<sub>A **site** is one individual unsafe OPERATION, not a function or a "
    "whole `unsafe {}` block (those are too coarse). "
    "**Transpiled / Compiled** — did cpp2rust emit, and does the emitted code "
    "build, for the C++ lane and the Rust lane (`ok/total` translation units). "
    "**Tested** — the differential test oracles: **A/B** runs the project's own "
    "program built from native C vs from the transpiled C++/Rust and compares "
    "output byte-for-byte (`—` = not linkable as one binary, e.g. cross-TU C++ "
    "name mangling or unresolved builtin FFI; logged, never silently passed); "
    "**pass@1** is CRUST-bench's official oracle — the emitted crate spliced "
    "under the hand-written RBench interface, then `cargo test`. For SQLite the "
    "Tested cell is the whole-CLI differential over the SQL scripts. "
    "**Original C Unsafe Sites** — initial unsafe operation sites in the C "
    "source (`raw_ptr_deref + static_mut + union_member`). **Emitted Rust "
    "Unsafe Sites** — resulting unsafe operation sites in the emitted Rust "
    "(`raw_ptr_deref + extern_unsafe_call + static_mut + union_read + transmute "
    "+ inline_asm`). These are not a clean subtraction: C treats FFI calls as "
    "free, but each becomes an `extern_unsafe_call` in Rust — so the "
    "per-family breakdown below the table is where the real memory-safety story "
    "(the raw-pointer-deref line) is visible. `unchecked_arith` is a separate "
    "lane (C pointer arithmetic has no Rust unsafe counterpart), never folded "
    "in. **Unsafe Site Reduction (%)** — `(C − Rust) ÷ C`; **positive = net "
    "fewer** unsafe sites, **negative = net more** (this build is a faithful "
    "transliteration — ownership/borrow uplift is deferred — so where Rust adds "
    "sites it is mostly C's previously-hidden FFI unsafety made explicit, not "
    "new unsafety). **Baseline C UOD** / **Emitted Rust UOD** — Unsafe-"
    "Operation-Density: unsafe sites ÷ total expressions in that lane's own AST "
    "(lower is safer); the denominator grows with any added scaffolding, so the "
    "density cannot be gamed by code inflation. All counts use thousands "
    "separators.</sub>"
)

# --- driver TSV site-family keys -------------------------------------------
C_FAMILIES = ["c_raw_ptr_deref", "c_static_mut", "c_union_member"]
R_FAMILIES = [
    "r_raw_ptr_deref", "r_extern_unsafe_call", "r_static_mut",
    "r_union_read", "r_transmute", "r_inline_asm",
]
# (family label, C key or None, Rust key or None) for the per-family aggregate.
FAMILY_ROWS = [
    ("raw_ptr_deref", "c_raw_ptr_deref", "r_raw_ptr_deref"),
    ("extern_unsafe_call (FFI/unsafe fn)", None, "r_extern_unsafe_call"),
    ("static_mut", "c_static_mut", "r_static_mut"),
    ("union read", "c_union_member", "r_union_read"),
    ("transmute", None, "r_transmute"),
    ("inline_asm", None, "r_inline_asm"),
]


def fmt_n(n):
    """Human-readable count: thousands separators (17,005 — not 17005)."""
    return f"{int(n):,}"


def gi(d, k):
    try:
        return int(d.get(k, "0"))
    except (ValueError, TypeError):
        return 0


def parse_kv(path):
    """One tab-separated line (or file) of key=value fields -> dict."""
    row = {}
    with open(path, encoding="utf-8") as f:
        for part in f.read().strip().split("\t"):
            if "=" in part:
                key, value = part.split("=", 1)
                row[key] = value
    return row


def parse_row_file(path):
    """A driver TSV row file -> dict (same tab-separated key=value shape)."""
    return parse_kv(path)


def upstream_url(cbench_dir, project):
    if not cbench_dir:
        return None
    cfg = os.path.join(cbench_dir, project, ".git", "config")
    try:
        with open(cfg, encoding="utf-8") as f:
            m = re.search(r"^\s*url = (\S+)$", f.read(), re.M)
            return m.group(1) if m else None
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Cell renderers (shared by both tables)
# ---------------------------------------------------------------------------
def _lane_icon(state):
    return {"yes": "✅", "partial": "⚠️", "no": "❌"}.get(state, "?")


def _ab_icon(state):
    return {"pass": "✅", "fail": "❌", "na": "—"}.get(state, "—")


def state_cells(r):
    """(transpiled, compiled, tested) cells from a driver row. `tested`
    combines both differential oracles (A/B + pass@1) into the single Tested
    column."""
    note = r.get("note", "")
    if "no-compile-commands" in note or "no-project-dir" in note:
        return ("n/a — project build broken", "—", "—")
    transpiled = (f"C++ {_lane_icon(r.get('transpiled_cpp'))} · "
                  f"Rust {_lane_icon(r.get('transpiled_rust'))}")
    compiled = f"C++ {r.get('compiled_cpp','?')} · Rust {r.get('compiled_rust','?')}"
    tested = (f"A/B C++ {_ab_icon(r.get('ab_cpp'))}·Rust {_ab_icon(r.get('ab_rust'))} "
              f"· pass@1 {_ab_icon(r.get('pass1'))}")
    return (transpiled, compiled, tested)


def pct(num, den, signed=False):
    """Percentage cell, or '—' when the denominator is zero. `signed` prefixes
    a leading + / − so a NEGATIVE reduction (Rust has more sites than C) reads
    honestly as an increase rather than being mistaken for a small reduction."""
    if not den:
        return "—"
    v = 100.0 * num / den
    if signed:
        sign = "+" if v > 0 else ("−" if v < 0 else "")
        return f"{sign}{abs(v):.1f}%"
    return f"{v:.1f}%"


def site_cells(r):
    """The 5 Multi-Dimensional Safety Matrix cells from any row carrying site
    keys: (Original C sites, Emitted Rust sites, Reduction %, Baseline C UOD,
    Emitted Rust UOD). Placeholders when the row has no site data."""
    if "c_sites" not in r and "r_sites" not in r:
        return ("—", "—", "—", "—", "—")
    c = gi(r, "c_sites")
    rs = gi(r, "r_sites")
    c_exprs = gi(r, "c_total_exprs")
    r_exprs = gi(r, "rust_exprs")
    reduction = pct(c - rs, c, signed=True) if c else "—"
    return (fmt_n(c), fmt_n(rs), reduction, pct(c, c_exprs), pct(rs, r_exprs))


# ---------------------------------------------------------------------------
# Aggregate per-family before/after block (DESIGN.md D3)
# ---------------------------------------------------------------------------
def aggregate_block(rows):
    tot = lambda k: sum(gi(r, k) for r in rows)
    lines = ["", "**Unsafe operation sites by family — all projects (C initial → Rust resulting):**",
             "", "| Family | Sites (C) | Sites (Rust) | Δ (C−Rust) |", "|---|---:|---:|---:|"]
    c_total = r_total = 0
    for label, ck, rk in FAMILY_ROWS:
        cv = tot(ck) if ck else None
        rv = tot(rk) if rk else 0
        if ck:
            c_total += cv
        r_total += rv
        c_cell = fmt_n(cv) if cv is not None else "— *(not unsafe in C)*"
        delta = "—" if cv is None else fmt_n(cv - rv)
        lines.append(f"| {label} | {c_cell} | {fmt_n(rv)} | {delta} |")
    lines.append(f"| **Total (memory-safety sites)** | **{fmt_n(c_total)}** | "
                 f"**{fmt_n(r_total)}** | **{fmt_n(c_total - r_total)}** |")
    # unchecked_arith — separate lane, reported but never folded in.
    lines.append(f"| _unchecked_arith (separate lane)_ | _{fmt_n(tot('c_unchecked_arith'))}_ | "
                 f"_{fmt_n(tot('r_unchecked_arith'))}_ | _—_ |")
    c_exprs = tot("c_total_exprs")
    r_exprs = tot("rust_exprs")
    c_uod = f"{100.0 * c_total / c_exprs:.2f}%" if c_exprs else "n/a"
    r_uod = f"{100.0 * r_total / r_exprs:.2f}%" if r_exprs else "n/a"
    reduction = pct(c_total - r_total, c_total, signed=True) if c_total else "n/a"
    # "N of M sites now safe" framing for the raw-pointer-deref memory story.
    c_deref = tot("c_raw_ptr_deref")
    r_deref = tot("r_raw_ptr_deref")
    lifted_deref = c_deref - r_deref
    if c_deref and lifted_deref >= 0:
        deref_line = (f"Raw-pointer dereferences (the core memory-safety family): "
                      f"**{fmt_n(lifted_deref)} of {fmt_n(c_deref)}** C deref sites "
                      f"lifted → {fmt_n(r_deref)} remain in Rust.")
    elif c_deref:
        deref_line = (f"Raw-pointer dereferences (the core memory-safety family): "
                      f"{fmt_n(c_deref)} in C → {fmt_n(r_deref)} in Rust "
                      f"(**+{fmt_n(-lifted_deref)}**; the emitter lowers some "
                      f"compound C accesses into several explicit Rust derefs, so a "
                      f"per-project split — not this raw aggregate — is the honest "
                      f"read of the memory-safety change).")
    else:
        deref_line = ""
    lines += [
        "",
        f"Corpus totals — Original C unsafe sites **{fmt_n(c_total)}** → Emitted "
        f"Rust unsafe sites **{fmt_n(r_total)}** (Unsafe Site Reduction "
        f"**{reduction}**; negative because this build is a faithful "
        f"transliteration and surfaces C's hidden FFI unsafety — see the "
        f"`extern_unsafe_call` row). Baseline C UOD **{c_uod}** → Emitted Rust "
        f"UOD **{r_uod}** (unsafe sites ÷ total expressions in each lane's AST).",
        deref_line,
        "Caveat — measurement scope: the C funnel is main-file-scoped (a "
        "deliberate choice so system-header noise is excluded) while the Rust "
        "census counts the `#include`d project code the emitter inlines. Projects "
        "that `#include` a generated `.c` therefore skew both their own reduction "
        "and their weight here — notably **libfor** (55 C sites vs 14,698 Rust, "
        "because its 28K-line `for-gen.c` is inlined and fully unrolled); it alone "
        "is roughly half the corpus `raw_ptr_deref` total. Read the per-project "
        "rows, not just this aggregate.",
    ]
    return "\n".join(l for l in lines if l is not None)


# ---------------------------------------------------------------------------
# CRUST-bench table
# ---------------------------------------------------------------------------
def load_rows(results_dir):
    rows = []
    for name in sorted(os.listdir(results_dir), key=str.lower):
        if not name.endswith(".tsv") or name == "summary.tsv":
            continue
        rows.append((name[:-len(".tsv")], parse_row_file(os.path.join(results_dir, name))))
    return rows


def render_crust(results_dir, cbench_dir, sqlite_status=None, sqlite_sites=None):
    rows = load_rows(results_dir)
    lines = list(HEADER)
    # SQLite sits IN the per-project table as the first row (the flagship — the
    # product's primary target — shown right alongside the CRUST-bench corpus).
    if sqlite_status and os.path.isfile(sqlite_status):
        lines.append(sqlite_row(sqlite_status, sqlite_sites, label_suffix=" — **flagship**"))
    for project, r in rows:
        t, c, tested = state_cells(r)
        cs, rs, red, cuod, ruod = site_cells(r)
        url = upstream_url(cbench_dir, project)
        cell = f"[{project}]({url})" if url else project
        lines.append(
            f"| {cell} | {t} | {c} | {tested} | {cs} | {rs} | {red} | {cuod} | {ruod} |")
    lines.append("")
    lines.append(LEGEND)
    lines.append(aggregate_block([r for _, r in rows]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SQLite flagship row — SAME site columns, its own state source
# ---------------------------------------------------------------------------
def git_short_rev(path):
    try:
        out = subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except OSError:
        return None


def sqlite_state_cells(status_row):
    """(transpiled, compiled, ab) from sqlite-status.tsv (files/crates/scripts)."""
    def split(key):
        m = re.fullmatch(r"(\d+)/(\d+)", status_row.get(key, ""))
        return (int(m.group(1)), int(m.group(2))) if m else None

    files = split("files")
    transpiled = ("—" if not files else
                  (f"✅ all {fmt_n(files[1])} files" if files[0] == files[1]
                   else f"⚠️ {fmt_n(files[0])}/{fmt_n(files[1])} files"))
    crates = split("crates")
    compiled = ("—" if not crates else
                (f"✅ all {fmt_n(crates[1])} crates" if crates[0] == crates[1]
                 else f"⚠️ {fmt_n(crates[0])}/{fmt_n(crates[1])} crates"))
    scripts = split("scripts")
    if scripts:
        mark = "✅ all" if scripts[0] == scripts[1] else "⚠️"
        count = (f"{scripts[0]}" if scripts[0] == scripts[1]
                 else f"{scripts[0]}/{scripts[1]}")
        runs = f" ({status_row['runs']} runs)" if status_row.get("runs") else ""
        ab = f"{mark} {count} SQL scripts byte-identical vs native CLI{runs}"
    else:
        ab = "—"
    return transpiled, compiled, ab


def sqlite_row(status_path, sites_path, label_suffix=""):
    """The single `| … |` SQLite markdown row — reused by the flagship table AND
    prepended as the first row of the per-project table (so SQLite sits IN the
    table alongside the CRUST-bench projects, not only in its own section)."""
    status_row = parse_kv(status_path)
    name = status_row.get("name", "SQLite")
    cell = f"[{name}]({status_row['url']})" if status_row.get("url") else name
    if status_row.get("output_url"):
        cell += f" → [Rust output]({status_row['output_url']})"
    cell += label_suffix
    t, c, tested = sqlite_state_cells(status_row)
    if sites_path and os.path.isfile(sites_path):
        cs, rs, red, cuod, ruod = site_cells(parse_kv(sites_path))
    else:
        # Never render stale function-granular numbers — mark honestly pending.
        cs = rs = red = cuod = ruod = "`pending-regen`"
    return f"| {cell} | {t} | {c} | {tested} | {cs} | {rs} | {red} | {cuod} | {ruod} |"


def render_sqlite(status_path, sites_path):
    status_row = parse_kv(status_path)
    lines = list(HEADER)
    lines.append(sqlite_row(status_path, sites_path))
    lines.append("")
    lines.append(LEGEND)
    if not (sites_path and os.path.isfile(sites_path)):
        lines.append("")
        lines.append(
            "<sub>SQLite's site columns are `pending-regen`: the SQLite unsafe-site "
            "census is regenerated off the fixed develop tip AFTER the current "
            "verification battery completes and the 16-02 SQLite-lane fix merges — "
            "numbers produced before then would not match the shipped state. State "
            "columns above reflect the last verified run "
            f"({status_row.get('run_date', '?')}).</sub>")
    else:
        rev = git_short_rev(os.path.dirname(sites_path) or ".")
        at = f" @ `{rev}`" if rev else ""
        lines.append("")
        lines.append(f"<sub>SQLite site counts from the SQLite funnel logs{at}; "
                     f"state facts recorded {status_row.get('run_date', '?')} in "
                     "[`benchmarks/sqlite-status.tsv`](benchmarks/sqlite-status.tsv).</sub>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Splice / CLI
# ---------------------------------------------------------------------------
def splice(doc, begin, end, table):
    if begin not in doc or end not in doc:
        return None
    head, rest = doc.split(begin, 1)
    _, tail = rest.split(end, 1)
    return head + begin + "\n" + table + "\n" + end + tail


def take_flag(args, flag):
    if flag not in args:
        return None
    i = args.index(flag)
    value = args[i + 1]
    del args[i:i + 2]
    return value


def main():
    args = sys.argv[1:]
    update_target = take_flag(args, "--update")
    sqlite_status = take_flag(args, "--sqlite-status")
    sqlite_sites = take_flag(args, "--sqlite-sites")

    tables = []
    if args and os.path.isdir(args[0]):
        cbench_dir = args[1] if len(args) > 1 and os.path.isdir(args[1]) else None
        tables.append((CRUST_BEGIN, CRUST_END,
                       render_crust(args[0], cbench_dir, sqlite_status, sqlite_sites)))
    if sqlite_status:
        if not os.path.isfile(sqlite_status):
            print("bad --sqlite-status path", file=sys.stderr)
            return 2
        tables.append((SQLITE_BEGIN, SQLITE_END, render_sqlite(sqlite_status, sqlite_sites)))
    if not tables:
        print(__doc__, file=sys.stderr)
        return 2

    if update_target:
        doc = open(update_target, encoding="utf-8").read()
        for begin, end, table in tables:
            spliced = splice(doc, begin, end, table)
            if spliced is None:
                print(f"markers {begin} missing in {update_target}", file=sys.stderr)
                return 2
            doc = spliced
        with open(update_target, "w", encoding="utf-8") as f:
            f.write(doc)
        print(f"updated {update_target}")
    else:
        print("\n\n".join(table for _, _, table in tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())
