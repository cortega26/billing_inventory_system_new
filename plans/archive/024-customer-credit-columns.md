# Plan 024: Reconcile customer schema drift — add `current_balance`/`credit_limit` to repo schema sources

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 131c2d7..HEAD -- models/customer.py schema.sql alembic/versions/ scripts/check_schema_drift.py tests/test_database/ tests/test_models/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2 (schema reconciliation; no code depends on the columns today)
- **Effort**: S
- **Risk**: LOW-MED (a migration that MUST be a no-op on the live DB — the inspector-guard is load-bearing)
- **Depends on**: none
- **Category**: migration
- **Planned at**: commit `131c2d7`, 2026-08-16

## Why this matters

The live El Rincón DB (`billing_inventory.db`) has two `customers` columns —
`current_balance INTEGER NOT NULL DEFAULT 0` and
`credit_limit INTEGER NOT NULL DEFAULT 50000 CHECK (credit_limit >= 0)` — that
exist in NO repo schema source (`schema.sql`, `models/customer.py`, both
Alembic revisions). Every live row is at the default (verified: 0 balances,
50000 credits). The drift was discovered by plan 023's executor (the copy
script's original excerpt assumed the columns existed everywhere). Because
fresh business DBs (e.g. `casabea.db`) are born from the repo schema, the two
business DBs now have different customer schemas — which will keep biting
tooling. `scripts/check_schema_drift.py` compares fresh `init_db()` vs
`SQLModel.metadata` only, so it can never see this class of drift.

**Decision (confirmed with the owner): reconcile by ADDING the columns to the
repo schema**, matching the live DB exactly. Zero data risk (all rows at
defaults; the live DB is untouched — the migration must be a no-op there).
The alternative — dropping the columns from the live DB — would destroy the
legacy lineage and is rejected per AGENTS.md ("do not destroy history
casually").

## Current state

Live DB DDL (verified via `sqlite_master`, `billing_inventory.db`; stamped at
`alembic_version = 72e1091bcd50` — the current head):

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT,
    current_balance INTEGER NOT NULL DEFAULT 0,
    credit_limit INTEGER NOT NULL DEFAULT 50000 CHECK (credit_limit >= 0),
    is_active INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT,
    CHECK (LENGTH(identifier_9) = 9),
    ...
)
```

Repo sources today (verified):

```sql
-- schema.sql:31-39
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE,
    name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    deleted_at TEXT
);
```

```python
# models/customer.py:34-41 — the two new fields must follow the is_active pattern
id: int | None = Field(default=None, primary_key=True)
identifier_9: str = Field(unique=True, index=True)
name: str | None = Field(default=None)
is_active: bool = Field(
    default=True,
    sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("1")),
)
deleted_at: str | None = Field(default=None)
# __table_args__ (lines 18-32) carries the named CheckConstraints.
# from_db_row (lines 79-82) uses row.get(...) with defaults — tolerant of
# missing columns, so existing callers are unaffected.
```

Migration head chain: `e318e5c02e34` (initial) → `72e1091bcd50` (head).
Existing revision style (read `alembic/versions/72e1091bcd50_*.py` before
writing): module docstring, `revision`/`down_revision` identifiers, plain
`op.execute`/`op.batch_alter_table` calls, idempotent where they touch both
fresh and legacy DBs.

Known additional drift (OUT OF SCOPE for this plan — record in notes, do not
touch): the live DB's `identifier_9 COLLATE NOCASE` and the `name`-length
CHECK differ from the repo definitions; the copy script and all services work
without them.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_database/test_customer_credit_columns.py` | all pass |
| Model tests | `.venv/bin/python -m pytest tests/test_models` | all pass |
| Schema drift | `.venv/bin/python scripts/check_schema_drift.py` | exit 0 |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `models/customer.py` — add the two fields + the credit_limit CHECK to `__table_args__`
- `schema.sql` — add the two columns to the customers DDL (match live exactly)
- `alembic/versions/` — NEW revision `add_customer_balance_credit_columns` (inspector-guarded, idempotent on the live DB)
- `tests/test_database/test_customer_credit_columns.py` — NEW
- `tests/test_models/test_customer_model.py` (or the existing customer-model test file) — defaults for the new fields

**Out of scope** (do NOT touch):
- The live `billing_inventory.db` — the migration must be a no-op on it when the app runs `upgrade head`; do not hand-edit it.
- The `identifier_9 COLLATE NOCASE` / `name`-CHECK drift (record as a backlog note in `plans/README.md`).
- `services/`, `ui/`, `config.py`, `scripts/copy_customers.py` (identity-only — unaffected), `scripts/check_schema_drift.py` (logic unchanged; it must simply keep passing).
- No product/feature code uses the columns — do not add any.

## Git workflow

- Branch: `advisor/024-customer-credit-columns`
- Commit per step; message style follows the repo (`feat:`/`fix:` for the model+schema+migration, `tests:` for tests)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Model + schema.sql

`models/customer.py`:
- Add fields after `deleted_at` (line 41), mirroring the `is_active` pattern:
  ```python
  current_balance: int = Field(
      default=0,
      sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
  )
  credit_limit: int = Field(
      default=50000,
      sa_column=sa.Column(
          sa.Integer, nullable=False, server_default=sa.text("50000")
      ),
  )
  ```
- Add to `__table_args__` (matching the live DB — note: `current_balance` has
  NO check in live; only `credit_limit` does):
  ```python
  sa.CheckConstraint("credit_limit >= 0", name="check_customer_credit_limit"),
  ```
- Do NOT add balance/limit validation to `post_init_validation` or
  `from_db_row` — leave them as plain fields (the live DB treats them as
  passive columns; no code reads them).

`schema.sql` — add to the customers CREATE TABLE (match live semantics
exactly, keep the repo's formatting style):
```sql
    current_balance INTEGER NOT NULL DEFAULT 0,
    credit_limit INTEGER NOT NULL DEFAULT 50000 CHECK (credit_limit >= 0),
```

**Verify**: `.venv/bin/python -m pytest tests/test_models` → all pass.

### Step 2: Migration (inspector-guarded — this is the load-bearing part)

Create `alembic/versions/<random12hex>_add_customer_balance_credit_columns.py`
(revision id: 12-hex via `python -c "import uuid; print(uuid.uuid4().hex[:12])"`,
`down_revision = "72e1091bcd50"`). Use `alembic.op`:

```python
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    """Add customer credit columns; no-op when they already exist (live DB)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("customers")}

    with op.batch_alter_table("customers") as batch_op:
        if "current_balance" not in existing:
            batch_op.add_column(
                sa.Column("current_balance", sa.Integer(), nullable=False,
                          server_default=sa.text("0"))
            )
        if "credit_limit" not in existing:
            batch_op.add_column(
                sa.Column("credit_limit", sa.Integer(), nullable=False,
                          server_default=sa.text("50000"))
            )
            batch_op.create_check_constraint(
                "check_customer_credit_limit", "credit_limit >= 0"
            )

def downgrade() -> None:
    """Drop the columns if present."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("customers")}
    with op.batch_alter_table("customers") as batch_op:
        if "credit_limit" in existing:
            batch_op.drop_constraint("check_customer_credit_limit", type_="check")
            batch_op.drop_column("credit_limit")
        if "current_balance" in existing:
            batch_op.drop_column("current_balance")
```

Rationale for the guard: the live DB is stamped at the head and already has
both columns — a plain `add_column` would crash on `duplicate column name`.
The guard makes the revision a no-op there and additive on fresh DBs.

**Verify**: `.venv/bin/python scripts/check_schema_drift.py` → exit 0 (fresh
`init_db()` now builds the new columns from schema.sql + migrations; model
metadata matches).

### Step 3: Migration tests

Create `tests/test_database/test_customer_credit_columns.py` (follow the
style of `tests/test_database/test_init_db.py` for driving `init_db` on temp
paths, and `tests/test_database/test_schema_constraints.py` for raw-SQL
assertions):

1. `test_fresh_db_has_columns_with_defaults` — `init_db(tmp path)`, then:
   - `PRAGMA table_info(customers)` includes both new columns;
   - insert a customer with only `(identifier_9, name)` → reads back
     `current_balance == 0`, `credit_limit == 50000`;
   - `INSERT ... credit_limit = -1` raises `sqlite3.IntegrityError` (CHECK).
2. `test_migration_is_noop_on_db_that_already_has_columns` — build a temp DB
   that simulates the live DB: create `customers` WITH the two columns and an
   `alembic_version` table stamped `72e1091bcd50` (plain sqlite3), then run
   the app's migration entry point (the same function `init_db` uses —
   check `database/migrations.py` for the exact callable and reuse it) →
   no error, columns unchanged, `alembic_version` now `72e...` + the new
   revision id.
3. `test_migration_adds_columns_to_pre_024_db` — same setup but the temp
   DB's `customers` WITHOUT the columns → after the migration the columns
   exist with the defaults.

**Verify**: `.venv/bin/python -m pytest tests/test_database/test_customer_credit_columns.py` → 3 passed.

### Step 4: Model test + full verification

In the existing customer-model test file (`tests/test_models/`): add a test
that `Customer()` has `current_balance == 0` and `credit_limit == 50000` by
default (and that constructing with explicit values round-trips).

**Verify**:
- `.venv/bin/python -m pytest tests/test_database tests/test_models` → all pass
- `.venv/bin/python -m pytest` → all pass (modulo any pre-existing worktree UI-test exceptions; 7 in `tests/test_ui/test_main_window_helpers.py` are known to fail in worktrees)
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean
- `.venv/bin/python scripts/check_schema_drift.py` → exit 0

## Test plan

| Test | File | Case |
|------|------|------|
| fresh DB has columns + defaults + CHECK | test_customer_credit_columns.py | schema shape, default values, negative-credit rejection |
| no-op on already-migrated DB | test_customer_credit_columns.py | live-DB simulation: upgrade runs clean, columns untouched |
| additive on pre-024 DB | test_customer_credit_columns.py | columns appear with defaults after upgrade |
| model defaults | tests/test_models/ | Customer() defaults + round-trip |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -c "current_balance" models/customer.py schema.sql` shows both updated; `credit_limit` likewise; `check_customer_credit_limit` present in the model's `__table_args__`
- [ ] New migration file exists with `down_revision = "72e1091bcd50"` and inspector-guarded `upgrade`/`downgrade`
- [ ] `.venv/bin/python scripts/check_schema_drift.py` exits 0
- [ ] `.venv/bin/python -m pytest tests/test_database/test_customer_credit_columns.py` exits 0 with 3 tests
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- The live DB's customer DDL differs from the excerpt (e.g. `current_balance`
  gains a CHECK) — report the actual DDL.
- `database/migrations.py`'s migration entry point isn't reusable from a test
  (report what it is instead of inventing a harness).
- A migration test reveals that `init_db` on a fresh DB produces columns that
  don't match `schema.sql` (that's the drift check's job — report).
- A step's verification fails twice after a reasonable fix attempt.
- You're tempted to touch `services/`, `ui/`, `config.py`, or the live
  `billing_inventory.db` — STOP instead.

## Maintenance notes

- After this lands, run the app once against the live El Rincón DB to confirm
  `alembic upgrade head` applies the no-op cleanly (the migration tests
  simulate it, but the real stamp+columns path deserves one manual boot).
- Record in `plans/README.md` (backlog): the remaining drift —
  `identifier_9 COLLATE NOCASE` and the name-length CHECK differ between the
  live DB and repo sources; a future plan may reconcile them the same way.
- `scripts/check_schema_drift.py` cannot see live-DB drift by construction; if
  this class of bug recurs, consider a `--compare-live` mode as a separate
  plan.
- Reviewer scrutiny: the inspector guard (both directions), that
  `current_balance` has no CHECK (matching live), and that the copy script's
  identity-only SELECTs are unaffected.
