#!/usr/bin/env python3
"""generate_report.py — turn a CRUST-bench run's per-project TSVs into the
per-project markdown table published in RESULTS.md.

Usage:
    benchmarks/generate_report.py <results-dir> [<cbench-dir>] [--update <RESULTS.md>]

With <cbench-dir> (the dataset's CBench folder), each project name links to
its upstream repository — resolved PROGRAMMATICALLY from the project's own
`.git/config` origin URL (every dataset project carries one); a project
without one is rendered unlinked, never guessed.

With --update, the table is spliced into the given markdown file between the
`<!-- crust-table:begin -->` / `<!-- crust-table:end -->` markers (the file's
table is never hand-edited — this script owns it).

Reads every `<results-dir>/<project>.tsv` row written by run_crust_bench.sh
(`summary.tsv` is skipped) and renders one table row per project with three
states:

  Transpiled  — did the converter turn the project's C into Rust?
                yes / partial (some files refused, loudly) / no / n/a (the
                project's own build is broken, so the converter never ran)
  Compiled    — how many of the emitted Rust crates compile (rustc, library
                object) — `12/12` style, so partial progress is visible.
  Tested      — the benchmark's own pass@1 metric (emitted Rust against the
                hand-written interface + its test suite). `not attempted`
                today, honestly, rather than a blended failure.
"""
import os
import re
import sys

FN_DEF = re.compile(r"^\s*(?:pub(?:\(crate\))?\s+)?(?:unsafe\s+)?(?:extern \"C\"\s+)?fn\s+\w+", re.M)

BEGIN = "<!-- crust-table:begin -->"
END = "<!-- crust-table:end -->"


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


def safety_counts(out_dir):
    """(total_fns, safe_fns, unsafe_sites) across every emitted .rs under
    out_dir — computed from the OUTPUT alone. A function is 'safe' when its
    body contains no `unsafe`; an 'unsafe site' is one `unsafe` occurrence
    (a block or an unsafe fn) — i.e. an operation whose safety could not be
    proven and is preserved, explicitly marked, instead of hidden."""
    total = safe = sites = 0
    for root, _dirs, files in os.walk(out_dir):
        for fname in files:
            if not fname.endswith(".rs"):
                continue
            try:
                text = open(os.path.join(root, fname), encoding="utf-8").read()
            except OSError:
                continue
            sites += text.count("unsafe")
            for m in FN_DEF.finditer(text):
                total += 1
                # body = balanced-brace span from the first { after the match
                i = text.find("{", m.end())
                if i < 0:
                    continue
                depth, j = 0, i
                while j < len(text):
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                body = text[m.start():j + 1]
                if "unsafe" not in body:
                    safe += 1
    return total, safe, sites


def parse_row(path):
    row = {"tier1": "", "tier2": "", "note": ""}
    with open(path, encoding="utf-8") as f:
        for part in f.read().strip().split("\t"):
            for key in ("tier1", "tier2", "note"):
                if part.startswith(key + "="):
                    row[key] = part[len(key) + 1:]
    return row


def states(row):
    """Map one TSV row to (transpiled, compiled, tested) cell texts."""
    note = row["note"]
    tested = "not attempted" if row["tier2"] in ("", "not-attempted") else row["tier2"]

    if "no-compile-commands" in note:
        return ("n/a — project's own build is broken", "—", "—")
    if row["tier1"] == "pass":
        return ("✅ yes", "✅ all", tested)
    m = re.search(r"crate-build-failed\((\d+)/(\d+)\)", note)
    if m:
        return ("✅ yes", f"⚠️ {m.group(1)}/{m.group(2)}", tested)
    m = re.search(r"transpile-partial\(crates=(\d+),compiled=(\d+)\)", note)
    if m:
        return ("⚠️ partial", f"⚠️ {m.group(2)}/{m.group(1)}", tested)
    if "transpile-failed" in note:
        return ("❌ no (refused, loudly)", "—", "—")
    return ("?", "?", tested)


def render(results_dir, cbench_dir):
    lines = [
        "| Project | Transpiled | Compiled | Tested | Fns | Fully safe | Unsafe sites |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in sorted(os.listdir(results_dir), key=str.lower):
        if not name.endswith(".tsv") or name == "summary.tsv":
            continue
        project = name[:-len(".tsv")]
        t, c, x = states(parse_row(os.path.join(results_dir, name)))
        url = upstream_url(cbench_dir, project)
        cell = f"[{project}]({url})" if url else project
        out_dir = os.path.join(results_dir, project, "out")
        if os.path.isdir(out_dir):
            total, safe, sites = safety_counts(out_dir)
        else:
            total = safe = sites = 0
        if total:
            pct = round(100.0 * safe / total)
            fns, safe_cell, sites_cell = str(total), f"{safe} ({pct}%)", str(sites)
        else:
            fns = safe_cell = sites_cell = "—"
        lines.append(f"| {cell} | {t} | {c} | {x} | {fns} | {safe_cell} | {sites_cell} |")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    update_target = None
    if "--update" in args:
        i = args.index("--update")
        update_target = args[i + 1]
        del args[i:i + 2]
    if not args or not os.path.isdir(args[0]):
        print(__doc__, file=sys.stderr)
        return 2
    results_dir = args[0]
    cbench_dir = args[1] if len(args) > 1 and os.path.isdir(args[1]) else None

    table = render(results_dir, cbench_dir)
    if update_target:
        doc = open(update_target, encoding="utf-8").read()
        if BEGIN not in doc or END not in doc:
            print(f"markers missing in {update_target}", file=sys.stderr)
            return 2
        head, rest = doc.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        with open(update_target, "w", encoding="utf-8") as f:
            f.write(head + BEGIN + "\n" + table + "\n" + END + tail)
        print(f"updated {update_target}")
    else:
        print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
