# Two-mode (non-safe vs safe) + per-function safety report — BUILD CONTRACT

Single source of truth for the zero-to-hero report pipeline. Every script component obeys the
schema/invocations/naming below EXACTLY so the pieces interlock. The runtime pipeline is a plain
script chain — **no AI/subagents at runtime**.

## 0. Axis (READ FIRST — corrects the old framing)

The report compares **two Rust emissions of the same program**, both scored by the SAME
`unsafe_census` instrument:

- **SAFE (uplift)** = production default, NO lab env vars. All uplift segments ON
  (pointer→Option/span, alloc→Box/Vec, printf→`print!`, cstring-global). This is what the
  current showcase already measures as "Emitted Rust". Reuse the existing `r_*` keys for it.
- **NON-SAFE (faithful)** = lab factory with all uplift segments dropped. NEW `f_*` keys.

Reduction = `(f_sites − r_sites) / f_sites` (signed). POSITIVE = the uplift removed unsafe sites.
This retires the old C-source-vs-Rust-output `−107.8%` framing.

## 1. Two emissions — SAME casing (critical for the per-function join)

Per project, from its `compile_commands.json` (`$CDB`), emit `--emit=rust` TWICE:

```sh
# SAFE (uplift / production default) — leave rustic casing at its production default (ON)
env -u C2R_LAB_FACTORY -u C2R_LAB_DROP_POINTER -u C2R_LAB_DROP_ALLOC \
    -u C2R_LAB_DROP_PRINTF -u C2R_LAB_DROP_CSTRING_GLOBAL \
    "$CPP2RUST" --cdb "$CDB" --emit=rust --out-dir "$SAFE_OUT"

# NON-SAFE (faithful) — drop all 4 uplift segments; DO NOT set C2R_RUSTIC_CASING=0
env C2R_LAB_FACTORY=1 C2R_LAB_DROP_POINTER=1 C2R_LAB_DROP_ALLOC=1 \
    C2R_LAB_DROP_PRINTF=1 C2R_LAB_DROP_CSTRING_GLOBAL=1 \
    "$CPP2RUST" --cdb "$CDB" --emit=rust --out-dir "$FAITHFUL_OUT"
```

RULE: **do NOT set `C2R_RUSTIC_CASING=0` in the faithful arm.** Both modes must keep identical
identifier casing so per-function `region=<file_stem>::<fn>` keys join 1:1. Casing contributes 0
unsafe sites; dropping it would only break the join.

## 2. Census

`"$UNSAFE_CENSUS" "$OUT" > census.<mode>.txt` (recursive over the emitted crate). Lines:
`FUNNEL_ACCT: lane=rust region=<stem>::<fn> raw_ptr_deref=N extern_unsafe_call=N first_party_call=N
intrinsic_call=N static_mut=N union_read=N transmute=N inline_asm=N unchecked_arith=N
unsafe_blocks=N total_exprs=N`, then one trailing `FUNNEL_ACCT: lane=rust parse_errors=N`.

## 3. Site total = 6 families ONLY

`site_total = raw_ptr_deref + extern_unsafe_call + static_mut + union_read + transmute + inline_asm`.
EXCLUDE `unchecked_arith`, `first_party_call`, `intrinsic_call`, `unsafe_blocks`. (Matches
`census.rs::site_total()` and the existing `r_sites` definition.)

## 4. Per-function metrics — bucket by LINE, never by distinct region string

(region keys can collide across same-named impl/trait methods — count lines.)
- `total_fns` = number of `region=` lines (use SAFE census; sanity-check vs faithful count).
- `unsafe_fns_<mode>` = region lines whose 6-family sum > 0.
- `fns_made_safe` = region-key JOIN: build `dict[region] → site_total` for each mode; count regions
  with `faithful.site_total > 0 AND safe.site_total == 0`. Exclude `first_party_call`/`intrinsic_call`
  from the sum.

## 5. Per-project TSV keys (append to `run_crust_project.sh::emit_row` fixed order)

Keep ALL existing keys (states, `c_*`, `r_*`, `rust_exprs`, `note`). `r_*` REMAINS the safe emission.
Add:
```
f_raw_ptr_deref f_extern_unsafe_call f_static_mut f_union_read f_transmute f_inline_asm
f_sites f_total_exprs
total_fns unsafe_fns_safe unsafe_fns_faithful fns_made_safe
safe_parse_errors faithful_parse_errors
compiled_rust_faithful   # ok/total ratio for the faithful crate build (may be n/a)
```
Reducers gate a project's SAFETY numbers as VALID only when
`safe_parse_errors==0 && faithful_parse_errors==0`. Otherwise the report renders `pending` /
`n/a(reason)` for that project's safety cells and the aggregate excludes it (report the exclusion count honestly).

## 6. Report (`generate_report.py`) — column set

`# | Project | Transpiled | Compiled | Tested | Non-safe Sites (faithful) | Safe Sites (uplift) |
Site Reduction (%) | Faithful UOD | Safe UOD | Total Fns | Unsafe Fns (faithful) |
Unsafe Fns (safe) | Fns Made Safe (n / %)`

- Column 1 `#` = 1-based sequential row number in render order (SQLite flagship = row 1, then
  projects 2..N). Left-aligned integer.

- Non-safe Sites = `f_sites`; Safe Sites = `r_sites`; Reduction = `pct(f_sites - r_sites, f_sites, signed=True)`.
- Faithful UOD = `f_sites/f_total_exprs`; Safe UOD = `r_sites/rust_exprs`.
- Fns Made Safe cell = `fns_made_safe` and `fns_made_safe/unsafe_fns_faithful` %.
- Project cell links the per-project **mirror** (see §8) when published, else upstream only.
- Rewrite LEGEND + prose from the C-vs-Rust "hidden FFI" story to "how many unsafe sites/functions
  the uplift REMOVES vs the faithful baseline". Note honestly that whole-program SQLite ≈0 delta
  (uplifts ABI-vetoed on externally-visible fns) and the signal concentrates in smaller projects.
- SQLite row: same schema, fed from `sqlite-sites.tsv` regenerated two-mode (§7).

## 7. SQLite two-mode

SQLite uses `~/Projects/.cache/sqlite-bench/compile_commands.json` (281 TUs). Emit both modes over
it (same env toggles), census both, fold into `benchmarks/sqlite-sites.tsv` with the SAME `r_*`/`f_*`
+ per-function keys via the SQLite reducer (`sqlite_sites_from_funnel.py`, re-pointed to two Rust
censuses). `sqlite-status.tsv` keeps state cells. Expect near-0 reduction (documented).

## 8. Per-project mirrors — PUBLIC + LICENSED + SUBMODULES OF THE SHOWCASE REPO

USER decisions: publish ALL 100 as PUBLIC repos, each carrying upstream license; each is a git
SUBMODULE **of the showcase repo** (`~/Projects/transpilers/clang2rust-showcase`), NOT of the
transpiler/main repo. The showcase is the public-facing bundle that links each report row to its
mirror.

- Repo: `o2alexanderfedin/<project>-rust-mirror` (public). Create-if-missing via
  `gh repo create ... --public` (idempotent; skip when it already exists).
- Submodule path **inside the showcase repo**: `mirrors/<project>-rust/` (so `.gitmodules` and the
  submodule pointers are committed to the SHOWCASE repo). SQLite's existing main-repo mirror wiring
  is left untouched; only these 100 CRUST mirrors are showcase submodules.
- Content = the **SAFE (uplift)** emitted Rust crate (rsync `-a --delete` excluding
  `.git README.md .gitignore target/`), only when SAFE emission is non-empty AND compiled.
- License propagation: copy the upstream root license file (case-insensitive
  `LICENSE* / COPYING* / LICENCE*`) from `CBench/<project>/` into the mirror. If NONE exists,
  write `NOTICE.md` stating no upstream root license file was found and linking the upstream repo
  (from `CBench/<project>/.git/config` origin). NEVER fabricate a license.
- `README.md`: "Generated artifact — do NOT hand-edit. Safe (uplift) Rust transpiled from
  <upstream_url> @ <upstream_commit> by clang2rust <ver>. Upstream license: <name|NONE-FOUND>."
- Guards (mirror the main-repo `bench/sync-mirrors.sh` template): origin-guarded (touch only
  `*-rust-mirror`), non-empty-guarded, diff-gated, dir-lock, non-fatal. Commit as `Alex Fedin
  <alex_fedin@hotmail.com>`, `git push origin HEAD:main`.
- After the mirror repo is pushed, `git submodule add`/update it into the SHOWCASE repo at
  `mirrors/<project>-rust/` and stage the pointer; the showcase commit (§9.7) bundles all pointer
  bumps + `.gitmodules`.
- Script location: `showcase/benchmarks/crust_mirror_publish.sh` (operates within the showcase
  repo). CLI (pinned so `run_all.sh` can call it):
  `crust_mirror_publish.sh --project <name> --safe-out <crate_dir> --cbench <CBench/project>
  --version <ver> [--publish]` (without `--publish` ⇒ dry-run: build the mirror tree + license
  locally, no `gh repo create`, no push, no submodule add).

## 9. Zero-to-hero entry `run_all.sh` (AI-free)

Ordered stages, each resumable/idempotent:
1. build `cpp2rust` (`cd cpp/build && ninja cpp2rust`) + `unsafe_census` (from `rust/`:
   `cargo build -p unsafe_census --release`).
2. ensure showcase on `main`; `fetch_dataset` (skips if cached).
3. two-mode sweep over all 100 projects (`run_crust_bench.sh` → `run_crust_project.sh`) + SQLite (§7).
4. reduce → per-project TSVs already carry all keys.
5. `generate_report.py ... --update RESULTS.md` (+ sqlite tsvs).
6. publish 100 mirrors (§8) as SHOWCASE submodules — gated behind `--publish` (default DRY-RUN/off).
7. commit the showcase repo (RESULTS.md + `.gitmodules` + all `mirrors/<project>-rust` pointer
   bumps) and push to both orgs. No transpiler-repo submodule bump for these.
Flags: `--only "p1 p2"`, `--subset N`, `--jobs N`, `--publish` (else dry-run publish),
`--no-sqlite`. Verification runs use `--subset` + no `--publish`.

## 10. Failure honesty (LOCKED project rule)

Faithful mode shifts translation burden onto c2ra's raw-form coverage, so some projects that
compile in safe mode may fail to emit/parse/compile in faithful mode. NEVER silently pass. Gate on
both-mode `parse_errors==0`; record excluded projects and show the count. Any newly-relied-on
number must be reproducible by re-running the script.
