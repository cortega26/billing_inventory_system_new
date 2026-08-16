# Plan 028: Resolve Codacy SQL-injection findings on scripts/ and a test

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 44c2fa5..HEAD -- scripts/check_schema_drift.py scripts/check_legacy_upgrade.py tests/test_services/test_business_switch.py tests/test_database/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2 (tooling hygiene — false positives, but keep the scanner clean)
- **Effort**: S
- **Risk**: LOW (behavior-identical query rewrites; scripts have real usage)
- **Depends on**: none
- **Category**: security (static-analysis hygiene)
- **Planned at**: commit `44c2fa5`, 2026-08-16

## Why this matters

Codacy reports six CRITICAL SQL-injection findings on f-string-built SQL in
`scripts/` and one test. All six interpolate **internal constants** — table
names from hardcoded tuples/dict keys (`STRIP_COLUMNS`, `CANONICAL_INDEXES`,
`SQLModel.metadata`, the test's own table list) — never user input, so none
are exploitable. Still, keeping the scanner clean matters: false positives
train the team to ignore CRITICALs. Four sites can be eliminated at the
source using SQLite's table-valued PRAGMA functions, which accept a BOUND
parameter (no f-string at all). The two `COUNT(*) FROM {table}` sites cannot
bind identifiers in SQL; they get the repo's documented suppression
convention (`# nosec B608`, per AGENTS.md — the only accepted suppression).
Note: bandit's scope (`-r database services utils`) excludes `scripts/`,
which is why only Codacy sees these.

## Current state

```python
# scripts/check_schema_drift.py:84 (_index_names)
rows = conn.execute(f"PRAGMA index_list({table})").fetchall()
# table ∈ metadata_tables & db_tables (closed sets from SQLModel.metadata + sqlite_master)

# scripts/check_schema_drift.py:117 (column comparison loop)
db_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}

# scripts/check_legacy_upgrade.py:112 (_assert_columns_restored)
actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
# table ∈ STRIP_COLUMNS.keys() (hardcoded dict)

# scripts/check_legacy_upgrade.py:127 (_assert_indexes)
actual = {row[1] for row in conn.execute(f"PRAGMA index_list({table})").fetchall() ...}
# table ∈ CANONICAL_INDEXES.keys() (hardcoded dict)

# scripts/check_legacy_upgrade.py:142 (_assert_quantity_types)
rows = conn.execute(
    f"SELECT typeof(quantity), COUNT(*) FROM {table} " ...
).fetchall()   # table ∈ ("sale_items", "purchase_items")

# tests/test_services/test_business_switch.py:72 (row-count helper)
count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
# table ∈ a hardcoded tuple defined in the test
```

SQLite's table-valued pragma functions return the same columns as the
PRAGMA statement and accept a bound parameter (SQLite ≥ 3.16; the repo's
Python 3.13 bundles ≥ 3.45):

- `SELECT * FROM pragma_table_info(?)` → columns `cid, name, type, notnull,
  dflt_value, pk` (same as `PRAGMA table_info`)
- `SELECT * FROM pragma_index_list(?)` → columns `seq, name, unique, origin,
  partial` (same as `PRAGMA index_list`)

Both scripts use `row["name"]`/`row[1]` access — unchanged with these
functions.

Repo conventions that apply:

- `# nosec B608` is the ONLY accepted suppression (AGENTS.md) and must carry
  a justification comment (see existing sites in `services/sale_service.py:202`).
- Scripts keep their plain-sqlite3, no-DatabaseManager style.
- Script behavior must be byte-identical: drift check must still pass, and
  the legacy-upgrade script's tests (`tests/test_database/` — locate the
  legacy-upgrade test file first) must stay green.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Drift check | `.venv/bin/python scripts/check_schema_drift.py` | exit 0 |
| Legacy tests | `.venv/bin/python -m pytest tests/test_database -k legacy` (adjust to the real test names) | all pass |
| Target tests | `.venv/bin/python -m pytest tests/test_services/test_business_switch.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `scripts/check_schema_drift.py` — the two PRAGMA sites
- `scripts/check_legacy_upgrade.py` — the three sites
- `tests/test_services/test_business_switch.py` — the COUNT site
- No test changes beyond the nosec comment; no new tests required (behavior
  unchanged) unless a site's refactor touches logic

**Out of scope** (do NOT touch):
- Any other script, service, or test file
- The `sqlite_master`-based queries elsewhere in `main.py` (not flagged; they
  are the same closed-set pattern — leave them)
- Codacy configuration (`.codacy/`) — no rule suppressions; fix at the source

## Git workflow

- Branch: `advisor/028-codacy-sqli-sites`
- Commit per step; message style follows the repo (`fix: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Bound pragma functions in check_schema_drift.py

Convert the two sites:

```python
# :84
rows = conn.execute("SELECT * FROM pragma_index_list(?)", (table,)).fetchall()

# :117
db_columns = {
    row["name"]
    for row in conn.execute("SELECT * FROM pragma_table_info(?)", (table,))
}
```

**Verify**: `.venv/bin/python scripts/check_schema_drift.py` → exit 0.

### Step 2: Bound pragma functions + nosec in check_legacy_upgrade.py

Convert the two PRAGMA sites (rows access stays `row[1]`):

```python
# :112
actual = {
    row[1]
    for row in conn.execute("SELECT * FROM pragma_table_info(?)", (table,)).fetchall()
}

# :127
actual = {
    row[1]
    for row in conn.execute("SELECT * FROM pragma_index_list(?)", (table,)).fetchall()
    if not row[1].startswith("sqlite_autoindex_")
}
```

The COUNT site keeps the f-string (identifiers cannot be bound) and gains
the documented suppression:

```python
# :142  table ∈ ("sale_items", "purchase_items") — hardcoded, not user input
rows = conn.execute(
    f"SELECT typeof(quantity), COUNT(*) FROM {table} "  # nosec B608
    "GROUP BY typeof(quantity)"
).fetchall()
```

**Verify**: locate and run the legacy-upgrade test(s) (grep `tests/` for
`check_legacy_upgrade` or `legacy`), then `.venv/bin/python -m pytest tests/test_database -k legacy` → all pass.

### Step 3: nosec on the test COUNT site

In `tests/test_services/test_business_switch.py:72`, the table comes from a
hardcoded tuple in the test itself:

```python
# table ∈ a hardcoded test tuple — not user input
count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # nosec B608
```

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_business_switch.py` → all pass.

### Step 4: Full verification

**Verify**:
- `grep -rn 'f"PRAGMA\|f"SELECT COUNT' scripts/ tests/` → only the two nosec sites remain (the `f"SELECT COUNT` in `scripts/check_legacy_upgrade.py` and `tests/test_services/test_business_switch.py`)
- `.venv/bin/python -m pytest` → all pass (modulo pre-existing worktree UI exceptions: 7 in `tests/test_ui/test_main_window_helpers.py`, 4 backup tests needing the live DB file)
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean
- `.venv/bin/python scripts/check_schema_drift.py` → exit 0

## Test plan

No new tests: the scripts' existing behavior is the verification (drift check
+ legacy-upgrade tests + business-switch tests all green). The nosec comments
document why each remaining site is safe.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -c 'pragma_table_info(?)' scripts/*.py` shows the two scripts converted (2 sites total)
- [ ] `grep -c 'pragma_index_list(?)' scripts/*.py` shows 2 sites
- [ ] Every remaining `f"PRAGMA` / `f"SELECT COUNT` in scripts/ and tests/ carries `# nosec B608` with a comment
- [ ] `.venv/bin/python scripts/check_schema_drift.py` exits 0
- [ ] `.venv/bin/python -m pytest tests/test_database -k legacy tests/test_services/test_business_switch.py` exits 0
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- The legacy-upgrade tests can't be located in `tests/` (report where they
  live instead of inventing new ones).
- A converted query returns different results than the PRAGMA form on the
  repo's SQLite version (verify with a quick probe before converting all
  sites; report if the table-valued function form fails).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- Future PRAGMA queries in scripts should use the table-valued function form
  with bound parameters — it removes the f-string entirely.
- Codacy may still flag the two nosec sites until its next scan; if it does,
  the `.codacy/` config could add an inline-ignore, but prefer keeping the
  repo-side comment as the single source of justification.
- Reviewer scrutiny: that the `pragma_*` result columns match the PRAGMA
  output (row access by name/index unchanged) and that no behavior changed
  in the drift or legacy checks.
