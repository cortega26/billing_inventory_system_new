# Plan 023: Copy customers from one business DB to another (El Rincón → CasaBea seed)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 17f9640..HEAD -- scripts/copy_customers.py tests/test_scripts/ config.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1 (requested feature — seed CasaBea with El Rincón's clients)
- **Effort**: S
- **Risk**: LOW (new CLI script; reads production data, writes only when explicitly invoked with `--target`; dry-run default)
- **Depends on**: none
- **Category**: feature
- **Planned at**: commit `17f9640`, 2026-08-15

## Why this matters

CasaBea (`casabea.cl`) starts with an empty customer list, while El Rincón de
Ébano has 127 customers — mostly the same building's residents, who are the
same people in both businesses today. The user decided (after an
architecture review) to keep the per-business-DB design and seed CasaBea with
a **one-time, idempotent customer copy**; a future one-way refresh can reuse
the same script. Never overwrite the target's existing data. Financial state
(`current_balance`) is NOT copied — debts are owed to El Rincón, not CasaBea.

## Current state

AMENDMENT (2026-08-15, after first execution attempt — STOPPED on DDL
mismatch): the ORIGINAL excerpt included `current_balance` and
`credit_limit`, which exist ONLY in the live El Rincón DB — they are absent
from `schema.sql`, `models/customer.py`, and both Alembic migrations, and
every live row is at its default (balance 0, credit 50000). The repo schema
is authoritative for the copy script (fresh business DBs, including
casabea.db, are born from it). Identity-only copy unaffected; balance/credit
handling dropped entirely (no columns, no flag). The live-vs-repo drift is
recorded as a separate backlog finding (plans/README.md) with a suggested
reconciliation plan.

The customer schema (repo sources, verified — `schema.sql:31-39`,
`models/customer.py:11-37`; a fresh `init_db()` target matches this):

```sql
customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE,   -- 9-digit phone, starts with '9'
    name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    deleted_at TEXT
)
customer_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identifier_3or4 TEXT NOT NULL        -- department id; row exists only when set
)
```

Facts verified on the live DB: 127 customers, each with one
`customer_identifiers` row (source SELECT reads only identity columns).

Existing script pattern to follow — `scripts/check_schema_drift.py` (lines
1-30): module docstring with usage, `PROJECT_ROOT` + `sys.path.insert`,
`# noqa: E402` on imports after the path insert, no third-party deps beyond
the app's own. `scripts/check_legacy_upgrade.py` opens `sqlite3` connections
directly with parameterized SQL — the same approach this script should take
(no `DatabaseManager` singleton juggling: the script touches two files and
the singleton would have to be re-pointed mid-run).

Validation helpers to reuse (from `utils/validation/validators.py`, verified
present): `validate_9digit_identifier`, `validate_3or4digit_identifier`
(raises `ValidationException` on bad input). Business DB paths resolve via
`config.get_business_db_path(business_id)` (plan 022, present on this branch).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| New tests | `.venv/bin/python -m pytest tests/test_scripts/test_copy_customers.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `scripts/copy_customers.py` — NEW CLI script + importable `copy_customers(...)` function
- `tests/test_scripts/__init__.py` — NEW (empty, mirrors `tests/` convention — verify `tests/__init__.py` exists first and mirror it)
- `tests/test_scripts/test_copy_customers.py` — NEW

**Out of scope** (do NOT touch):
- `services/` (especially `customer_service.py`), `ui/`, `config.py`, `database/` — the script reads/writes raw tables and reuses validators only. No audit-log rows, no event emission (the script is headless; the app is not running when it's used).
- The production `billing_inventory.db` / any real business DB — tests use `tmp_path` files only; the script itself is only run against real DBs when the operator invokes it.
- Any schema/migration change.

## Git workflow

- Branch: `advisor/023-copy-customers`
- Commit per step; message style follows the repo (`feat: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Write the script

Create `scripts/copy_customers.py` with:

1. Module docstring + CLI usage, mirroring `check_schema_drift.py`'s header
   (PROJECT_ROOT + `sys.path.insert`, `# noqa: E402` imports).
2. Imports: `sqlite3`, `argparse`, `sys`, `Path`; `config` (for business
   paths); `from utils.validation.validators import validate_9digit_identifier,
   validate_3or4digit_identifier`; `from utils.exceptions import
   ValidationException`.
3. A pure, importable function (this is what tests exercise):

```python
def copy_customers(
    source_path: Path,
    target_path: Path,
    include_inactive: bool = False,
) -> dict[str, int]:
    """Copy customers (identity only) from source DB to target DB.

    Idempotent: existing identifier_9 values in the target are never
    overwritten. The copy is identity-only: identifier_9, name, is_active,
    and identifier_3or4. Returns a summary dict
    {"inserted": int, "existing": int, "invalid": int}.
    """
```

   Behavior:
   - Open plain `sqlite3` connections to both files (row_factory=Row for
     source). Read all source customers (with their identifier_3or4 via a
     LEFT JOIN or a second query), filtering `is_active = 1` unless
     `include_inactive`.
   - For each source customer: if `identifier_9` already exists in target →
     count as "existing", skip. Otherwise validate both identifiers through
     the validators; on `ValidationException` → count as "invalid", log, skip
     (never let one bad row abort the whole run).
   - Insert into target inside a single transaction: `INSERT INTO customers
     (identifier_9, name, is_active) VALUES (?, ?, ?)` (SOURCE VALUES: do not
     select balance/limit columns even though the live source DB has them —
     read only `identifier_9, name, is_active`), then `INSERT INTO
     customer_identifiers (customer_id, identifier_3or4) VALUES (?, ?)`
     (use `lastrowid`) ONLY when identifier_3or4 is present and non-empty
     (the target column is NOT NULL; a missing source value means no row).
   - Also `CREATE TABLE IF NOT EXISTS` is NOT the script's job — document
     that the target DB must exist and be migrated (run `init_db()` on it
     once, e.g. by opening the business in the app or
     `python -c "from database import init_db; init_db('<target>')"`).
     Guard anyway: if `target_path` doesn't exist or lacks the `customers`
     table, fail with a clear error message.
4. `main()` with argparse: `--source PATH` (default:
   `config.get_business_db_path("default")`), `--target PATH` (default:
   `config.get_business_db_path("casabea")` — error out with a clear message
   if the business id isn't registered), `--include-inactive` (flag),
   `--dry-run` (flag: report inserted/existing counts without writing).
5. Spanish user-facing messages (repo convention).

**Verify**: `.venv/bin/python scripts/copy_customers.py --help` → exit 0 and
shows all five options.

### Step 2: Tests

Create `tests/test_scripts/__init__.py` (empty; check `tests/__init__.py`
exists and mirror it) and `tests/test_scripts/test_copy_customers.py` with
real temp DB files (`tmp_path`), building schemas via plain sqlite3 with the
exact `customers`/`customer_identifiers` DDL from "Current state":

- `test_copies_active_customers_with_department_ids` — seed 2 active
  customers (one with identifier_3or4), run `copy_customers`, assert target
  has both, with names/is_active/identifier_3or4 preserved and
  `current_balance == 0`.
- `test_is_idempotent_and_never_overwrites` — run twice; second run inserts
  0; a target customer with a modified name stays modified (source change
  ignored).
- `test_skips_inactive_by_default_and_includes_with_flag` — seeded archived
  customer (is_active=0) not copied by default, copied with
  `include_inactive=True`.
- `test_invalid_identifier_is_counted_not_aborted` — seed a customer with an
  invalid identifier_9 (e.g. not starting with '9'); assert run completes,
  `invalid == 1`, other customers still inserted.
- `test_dry_run_writes_nothing` — `--dry-run` path: call the function's
  reporting with a flag or subprocess the CLI with `--dry-run`; assert target
  unchanged. (Prefer invoking `main()` via argparse with a patched sys.argv
  or subprocess — your choice, keep it deterministic.)
- `test_skips_identifier_row_when_3or4_missing` — a source customer without
  an identifier_3or4 lands with NO `customer_identifiers` row (NOT NULL
  target column not violated).

**Verify**: `.venv/bin/python -m pytest tests/test_scripts/test_copy_customers.py` → all pass.

### Step 3: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass (modulo any pre-existing worktree UI-test exceptions — none in scope here)
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0

## Test plan

| Test | File | Case |
|------|------|------|
| copies active customers + dept ids | test_copy_customers.py | identity preserved, balance zeroed |
| idempotent, never overwrites | test_copy_customers.py | re-run inserts 0; target edits survive |
| inactive default/flag | test_copy_customers.py | skipped by default, copied with flag |
| invalid row counted, not aborted | test_copy_customers.py | run completes, invalid==1 |
| dry-run writes nothing | test_copy_customers.py | target unchanged |
| missing 3or4 → no identifier row | test_copy_customers.py | NOT NULL target respected |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `scripts/copy_customers.py` exists with an importable `copy_customers()` and a `main()` with the four CLI options (--source, --target, --include-inactive, --dry-run)
- [ ] `.venv/bin/python scripts/copy_customers.py --help` exits 0
- [ ] `.venv/bin/python -m pytest tests/test_scripts/test_copy_customers.py` exits 0 with the six tests above
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- The `customers`/`customer_identifiers` DDL doesn't match the excerpt (schema changed) — report instead of adapting.
- The validators' names differ from the excerpt (`validate_9digit_identifier`, `validate_3or4digit_identifier`).
- A step's verification fails twice after a reasonable fix attempt.
- You're tempted to touch `services/`, `ui/`, `config.py`, or `database/` — STOP instead.

## Maintenance notes

- This script IS the future one-way refresh: re-running it copies only *new*
  El Rincón customers into CasaBea, never overwriting. Bidirectional sync is
  deliberately out of scope (documented decision: the client bases are
  diverging).
- When casabea.cl's online store eventually lands (user is building it), this
  script's idempotent import becomes the seed/backfill path for that
  channel's customer master — keep the "never overwrite" rule when extending
  it.
- Reviewer scrutiny: that the copy runs in one transaction on the target,
  reads only identity columns from the source (the live source DB has extra
  balance/credit columns that must NOT be selected or copied), and that the
  CLI defaults resolve via `config.get_business_db_path` with a clear error
  for an unregistered business id.
