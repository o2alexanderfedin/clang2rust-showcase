#!/usr/bin/env python3
"""sqlite_sites_from_funnel.py <funnel_c.log> <funnel_rust.log>

Fold the SQLite unsafe-site funnel logs into the ONE-LINE site TSV that
generate_report.py consumes via `--sqlite-sites` (same driver row schema as a
CRUST-bench project, so SQLite renders in the SAME site-granular columns).

  funnel_c.log     — `cpp2rust --cdb <sqlite CDB> --emit=funnel-ingest`
                     lines: `FUNNEL_ACCT: lane=c region=… raw_ptr_deref=…
                     static_mut=… union_member=… unchecked_arith=…`
  funnel_rust.log  — `unsafe_census <emitted SQLite Rust OUTROOT>`
                     lines: `FUNNEL_ACCT: lane=rust region=… raw_ptr_deref=…
                     extern_unsafe_call=… static_mut=… union_read=… transmute=…
                     inline_asm=… unchecked_arith=… unsafe_blocks=… total_exprs=…`

Emits one tab-separated key=value line to stdout. Redirect it to
`benchmarks/sqlite-sites.tsv` and pass that path to
`generate_report.py --sqlite-sites`.

IMPORTANT: this is a pure reducer over already-produced logs — it does NOT run
the SQLite corpus or the funnel itself (that must happen off the fixed develop
tip after the verification battery + 16-02, per the orchestrator's plan).
"""
import re
import sys


def sum_key(path, key):
    total = 0
    rx = re.compile(rf"\b{re.escape(key)}=(\d+)\b")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                for m in rx.finditer(line):
                    total += int(m.group(1))
    except OSError as e:
        print(f"warning: {e}", file=sys.stderr)
    return total


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    fc, fr = sys.argv[1], sys.argv[2]

    c = {k: sum_key(fc, k) for k in
         ("raw_ptr_deref", "static_mut", "union_member", "unchecked_arith", "total_exprs")}
    r = {k: sum_key(fr, k) for k in
         ("raw_ptr_deref", "extern_unsafe_call", "first_party_call", "intrinsic_call",
          "static_mut", "union_read", "transmute", "inline_asm", "unchecked_arith",
          "unsafe_blocks", "total_exprs")}

    fields = {
        "project": "sqlite",
        "c_raw_ptr_deref": c["raw_ptr_deref"],
        "c_static_mut": c["static_mut"],
        "c_union_member": c["union_member"],
        "c_unchecked_arith": c["unchecked_arith"],
        "c_sites": c["raw_ptr_deref"] + c["static_mut"] + c["union_member"],
        "c_total_exprs": c["total_exprs"],
        "r_raw_ptr_deref": r["raw_ptr_deref"],
        "r_extern_unsafe_call": r["extern_unsafe_call"],
        "r_first_party_call": r["first_party_call"],
        "r_intrinsic_call": r["intrinsic_call"],
        "r_static_mut": r["static_mut"],
        "r_union_read": r["union_read"],
        "r_transmute": r["transmute"],
        "r_inline_asm": r["inline_asm"],
        "r_unchecked_arith": r["unchecked_arith"],
        "r_unsafe_blocks": r["unsafe_blocks"],
        "r_sites": (r["raw_ptr_deref"] + r["extern_unsafe_call"] + r["static_mut"]
                    + r["union_read"] + r["transmute"] + r["inline_asm"]),
        "rust_exprs": r["total_exprs"],
    }
    print("\t".join(f"{k}={v}" for k, v in fields.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
