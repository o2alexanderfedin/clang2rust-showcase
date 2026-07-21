#!/usr/bin/env python3
"""generate_report.py — render the per-project markdown tables published in
RESULTS.md from result files. This script owns every table; none is
hand-edited.

Usage:
    benchmarks/generate_report.py <results-dir> [<cbench-dir>]
        [--sqlite-status <tsv> --sqlite-src <dir>] [--update <RESULTS.md>]

CRUST-bench table — reads every `<results-dir>/<project>.tsv` row written by
run_crust_bench.sh (`summary.tsv` is skipped) and renders one row per project.
With <cbench-dir> (the dataset's CBench folder), each project name links to
its upstream repository — resolved PROGRAMMATICALLY from the project's own
`.git/config` origin URL (every dataset project carries one); a project
without one is rendered unlinked, never guessed.

SQLite flagship table — `--sqlite-status` names a small tab-separated
key=value file recording the verified run facts (files converted, crates
compiled, differential scripts passed); `--sqlite-src` points at a checkout
of the published Rust output, over which the safety columns are computed by
the same counting code as the CRUST-bench table.

With --update, each rendered table is spliced into the given markdown file
between its `<!-- crust-table:begin/end -->` / `<!-- sqlite-table:begin/end -->`
markers.

Column meanings (shared by both tables):

  Transpiled  — did the converter turn the project's C into Rust?
                yes / partial (some files refused, loudly) / no / n/a (the
                project's own build is broken, so the converter never ran)
  Compiled    — how many of the emitted Rust crates compile (rustc, library
                object) — `12/12` style, so partial progress is visible.
  Tested      — CRUST-bench: the benchmark's own pass@1 metric (`not
                attempted` today, honestly). SQLite: end-to-end differential
                testing — transpiled CLI vs native CLI over the same SQL
                scripts, outputs compared byte-for-byte.
  Functions   — function DEFINITIONS in the emitted Rust (declarations of
                foreign functions in `extern` blocks are not counted).
  Fully safe functions — definitions that are not `unsafe fn` and whose body
                contains no `unsafe` block; shown as count + share of all
                functions.
  `unsafe` sites — `unsafe` blocks plus `unsafe fn` definitions in the output
                (linkage declarations and attribute spellings such as
                `#[unsafe(no_mangle)]` are not operations and not counted).
  All counts are rendered with thousands separators; every table carries a
  one-line legend so the columns are self-explanatory in RESULTS.md itself.
"""
import os
import re
import subprocess
import sys

FN_DEF = re.compile(
    r"^\s*(?:pub(?:\(crate\))?\s+)?(?:const\s+)?(unsafe\s+)?"
    r"(?:extern \"C\"\s+)?fn\s+\w+",
    re.M,
)
UNSAFE_BLOCK = re.compile(r"\bunsafe\s*\{")

CRUST_BEGIN = "<!-- crust-table:begin -->"
CRUST_END = "<!-- crust-table:end -->"
SQLITE_BEGIN = "<!-- sqlite-table:begin -->"
SQLITE_END = "<!-- sqlite-table:end -->"

HEADER = [
    "| Project | Transpiled | Compiled | Tested | Functions "
    "| Fully safe functions | `unsafe` sites |",
    "|---|---|---|---|---|---|---|",
]

# One-line legend rendered under BOTH tables (generator-owned, inside the
# splice markers) so every number is defined right where it is read.
LEGEND = (
    "<sub>**Functions** — function definitions in the generated Rust "
    "(declarations of external C functions are not counted). "
    "**Fully safe functions** — functions with no `unsafe` anywhere: not "
    "declared `unsafe fn` and containing no `unsafe` block; the percentage "
    "is their share of all functions. "
    "**`unsafe` sites** — individual `unsafe` blocks or `unsafe fn` "
    "definitions remaining in the output; each marks one place whose safety "
    "is inherited from the original C rather than proven by the Rust "
    "compiler (fewer is better).</sub>"
)


def fmt_n(n):
    """Human-readable count: thousands separators (17,005 — not 17005)."""
    return f"{n:,}"


def upstream_url(cbench_dir, project):
    """Origin URL from the project's own .git/config, or None."""
    if not cbench_dir:
        return None
    cfg = os.path.join(cbench_dir, project, ".git", "config")
    try:
        with open(cfg, encoding="utf-8") as f:
            m = re.search(r"^\s*url = (\S+)$", f.read(), re.M)
            return m.group(1) if m else None
    except OSError:
        return None


def body_span(text, sig_end):
    """(open_brace, close_brace) of the definition body starting after the
    signature, or None when the signature ends in `;` first — i.e. a
    declaration (an `extern` block import), not a definition."""
    brace = text.find("{", sig_end)
    semi = text.find(";", sig_end)
    if brace < 0 or (0 <= semi < brace):
        return None
    depth, j = 0, brace
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return brace, j
        j += 1
    return brace, len(text) - 1


def safety_counts(out_dir):
    """(total_fns, safe_fns, unsafe_sites) across every emitted .rs under
    out_dir — computed from the OUTPUT alone. Only function DEFINITIONS
    count (declarations inside `extern` blocks do not); an 'unsafe site' is
    an `unsafe` block or an `unsafe fn` definition — an operation whose
    safety could not be proven and is preserved, explicitly marked, instead
    of hidden. `unsafe extern` linkage and `#[unsafe(...)]` attributes are
    spellings, not operations, and are not counted."""
    total = safe = sites = 0
    for root, _dirs, files in os.walk(out_dir):
        if ".git" in root.split(os.sep):
            continue
        for fname in files:
            if not fname.endswith(".rs"):
                continue
            try:
                text = open(os.path.join(root, fname), encoding="utf-8").read()
            except OSError:
                continue
            sites += len(UNSAFE_BLOCK.findall(text))
            for m in FN_DEF.finditer(text):
                span = body_span(text, m.end())
                if span is None:
                    continue
                total += 1
                if m.group(1):  # `unsafe fn` definition
                    sites += 1
                    continue
                if not UNSAFE_BLOCK.search(text[span[0]:span[1] + 1]):
                    safe += 1
    return total, safe, sites


def safety_cells(out_dir):
    if not os.path.isdir(out_dir):
        return "—", "—", "—"
    total, safe, sites = safety_counts(out_dir)
    if not total:
        return "—", "—", "—"
    pct = round(100.0 * safe / total)
    return fmt_n(total), f"{fmt_n(safe)} ({pct}%)", fmt_n(sites)


def parse_kv(path):
    """One tab-separated line of key=value fields -> dict."""
    row = {}
    with open(path, encoding="utf-8") as f:
        for part in f.read().strip().split("\t"):
            if "=" in part:
                key, value = part.split("=", 1)
                row[key] = value
    return row


def states(row):
    """Map one CRUST TSV row to (transpiled, compiled, tested) cell texts."""
    note = row.get("note", "")
    tier2 = row.get("tier2", "")
    tested = "not attempted" if tier2 in ("", "not-attempted") else tier2

    if "no-compile-commands" in note:
        return ("n/a — project's own build is broken", "—", "—")
    if row.get("tier1") == "pass":
        return ("✅ yes", "✅ all", tested)
    m = re.search(r"crate-build-failed\((\d+)/(\d+)\)", note)
    if m:
        return ("✅ yes", f"⚠️ {m.group(1)} of {m.group(2)} crates", tested)
    m = re.search(r"transpile-partial\(crates=(\d+),compiled=(\d+)\)", note)
    if m:
        return ("⚠️ partial", f"⚠️ {m.group(2)} of {m.group(1)} crates", tested)
    if "transpile-failed" in note:
        return ("❌ no (refused, loudly)", "—", "—")
    return ("?", "?", tested)


def render_crust(results_dir, cbench_dir):
    lines = list(HEADER)
    for name in sorted(os.listdir(results_dir), key=str.lower):
        if not name.endswith(".tsv") or name == "summary.tsv":
            continue
        project = name[:-len(".tsv")]
        t, c, x = states(parse_kv(os.path.join(results_dir, name)))
        url = upstream_url(cbench_dir, project)
        cell = f"[{project}]({url})" if url else project
        fns, safe_cell, sites_cell = safety_cells(
            os.path.join(results_dir, project, "out"))
        lines.append(f"| {cell} | {t} | {c} | {x} | {fns} | {safe_cell} | {sites_cell} |")
    lines.append("")
    lines.append(LEGEND)
    return "\n".join(lines)


def ratio_cells(row):
    """Render the SQLite status facts, honestly reflecting any shortfall."""
    def split(key):
        m = re.fullmatch(r"(\d+)/(\d+)", row.get(key, ""))
        return (int(m.group(1)), int(m.group(2))) if m else None

    files = split("files")
    if files:
        if files[0] == files[1]:
            transpiled = f"✅ yes — all {fmt_n(files[1])} C source files"
        else:
            transpiled = (f"⚠️ partial — {fmt_n(files[0])} of "
                          f"{fmt_n(files[1])} C source files")
    else:
        transpiled = "?"

    crates = split("crates")
    if crates:
        compiled = (f"✅ all {fmt_n(crates[1])} crates"
                    if crates[0] == crates[1]
                    else f"⚠️ {fmt_n(crates[0])} of {fmt_n(crates[1])} crates")
    else:
        compiled = "?"

    scripts = split("scripts")
    if scripts:
        mark = "✅ all" if scripts[0] == scripts[1] else "⚠️"
        count = (f"{scripts[0]}" if scripts[0] == scripts[1]
                 else f"{scripts[0]} of {scripts[1]}")
        runs = (f" ({row['runs']} independent runs)"
                if row.get("runs") else "")
        tested = (f"{mark} {count} SQL test scripts byte-identical "
                  f"vs the native CLI{runs}")
    else:
        tested = "?"
    return transpiled, compiled, tested


def git_short_rev(path):
    try:
        out = subprocess.run(
            ["git", "-C", path, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except OSError:
        return None


def render_sqlite(status_path, src_dir):
    row = parse_kv(status_path)
    name = row.get("name", "?")
    cell = f"[{name}]({row['url']})" if row.get("url") else name
    if row.get("output_url"):
        cell += f" → [Rust output]({row['output_url']})"
    t, c, x = ratio_cells(row)
    fns, safe_cell, sites_cell = safety_cells(src_dir)
    lines = list(HEADER)
    lines.append(f"| {cell} | {t} | {c} | {x} | {fns} | {safe_cell} | {sites_cell} |")
    lines.append("")
    lines.append(LEGEND)
    rev = git_short_rev(src_dir)
    at = f" @ `{rev}`" if rev else ""
    lines.append("")
    lines.append(f"Safety columns computed over the published Rust output{at}; "
                 f"run facts recorded {row.get('run_date', '?')} in "
                 f"[`benchmarks/sqlite-status.tsv`](benchmarks/sqlite-status.tsv).")
    return "\n".join(lines)


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
    sqlite_src = take_flag(args, "--sqlite-src")

    tables = []  # (begin_marker, end_marker, rendered)
    if args and os.path.isdir(args[0]):
        cbench_dir = args[1] if len(args) > 1 and os.path.isdir(args[1]) else None
        tables.append((CRUST_BEGIN, CRUST_END, render_crust(args[0], cbench_dir)))
    if sqlite_status and sqlite_src:
        if not os.path.isfile(sqlite_status) or not os.path.isdir(sqlite_src):
            print("bad --sqlite-status / --sqlite-src paths", file=sys.stderr)
            return 2
        tables.append((SQLITE_BEGIN, SQLITE_END, render_sqlite(sqlite_status, sqlite_src)))
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
