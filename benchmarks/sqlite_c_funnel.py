#!/usr/bin/env python3
"""sqlite_c_funnel.py <compile_commands.json> <out.log> [--bin PATH] [--jobs N]

Produce the SQLite C-side unsafe-site funnel log (one FUNNEL_ACCT line per
main-file function) that feeds sqlite_sites_from_funnel.py.

It runs `cpp2rust --emit=funnel-ingest` over the corpus ONE TU at a time, each
through the SAME multi-file `--cdb` path using a one-entry compile DB — never a
separate "single-file mode" (single-file == multi-file with one file), and with
a single worker per invocation it also sidesteps the multi-worker `--cdb`
arena-UAF that intermittently aborts a whole-corpus run.

Read-only over the C sources; writes only to <out.log>. Run this once the SQLite
verification state is stable, then:

    python3 benchmarks/sqlite_c_funnel.py "$SQLITE_CDB" funnel_c.log
    unsafe_census "$SQLITE_RUST_MIRROR"                > funnel_rust.log
    python3 benchmarks/sqlite_sites_from_funnel.py funnel_c.log funnel_rust.log \
        > benchmarks/sqlite-sites.tsv
"""
import json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor


def main():
    args = sys.argv[1:]
    binp = "cpp2rust"
    jobs = 3
    if "--bin" in args:
        i = args.index("--bin"); binp = args[i + 1]; del args[i:i + 2]
    if "--jobs" in args:
        i = args.index("--jobs"); jobs = int(args[i + 1]); del args[i:i + 2]
    if len(args) != 2:
        print(__doc__, file=sys.stderr); return 2
    cdb_path, out_path = args
    entries = json.load(open(cdb_path))

    def run_one(entry):
        fd, path = tempfile.mkstemp(suffix=".json", prefix="cdb1_")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump([entry], f)
            r = subprocess.run([binp, "--cdb", path, "--emit=funnel-ingest"],
                               capture_output=True, text=True, timeout=180)
            return entry.get("file", "?"), r.stdout, r.returncode
        except Exception as e:
            return entry.get("file", "?"), f"# ERROR {entry.get('file')}: {e}\n", -1
        finally:
            os.unlink(path)

    done = errs = 0
    with open(out_path, "w") as fh, ThreadPoolExecutor(max_workers=jobs) as ex:
        for _f, out, rc in ex.map(run_one, entries):
            fh.write(out)
            done += 1
            if rc != 0:
                errs += 1
    print(f"sqlite_c_funnel: {done} TUs ({errs} nonzero rc) -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
