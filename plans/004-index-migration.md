# Plan 004: Reconcile index sources, cleanup migration, quantity-type normalization, legacy-upgrade test

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: the repo has uncommitted changes; the excerpts
> below reflect the working tree. Open each cited file and confirm the excerpt
> matches. On a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: migration / tech-debt
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

The schema has THREE parallel sources that must stay in sync (schema.sql,
SQLModel.metadata, Alembic migrations), and two have drifted:

1. **schema.sql's entire index block is dead code.** `database/__init__.py:77-89`
   (`_load_table_statements`) filters `schema.sql` to `CREATE TABLE` statements
   only, so the 10 `CREATE INDEX` statements at `schema.sql:115-127` are never
   applied to fresh installs. Verified: a fresh `init_db()` DB lacks
   `idx_sale_items_composite`, `idx_sale_items_product_id`, `idx_sales_date_customer`
   — fresh and legacy installs get different index sets.
2. **The real DB carries ~12 duplicate indexes.** The initial migration
   (`alembic/versions/e318e5c02e34_initial_schema.py:124-159`) only issues
   `CREATE INDEX IF NOT EXISTS`; `downgrade()` is `pass`. Real `billing_inventory.db`
   has, e.g., `sale_items` with 6 indexes where `idx_sale_items_sale` ≡
   `idx_sale_items_sale_id` and `idx_sale_items_composite` ≡ `idx_sale_items_sale_product`
   (identical definitions, different names), `sales` with 8, plus a STALE index
   `idx_categories_parent_id` on `categories` which has no `parent_id` column.
   Every write maintains 2-3x the needed index entries on the hottest tables.
3. **Quantity values are stored mixed-typed.** `create_sale` writes
   `float(item["quantity"])` (`services/sale_service.py:76-86`) but the update
   path and all purchase inserts write `str(round(float(q), 3))`
   (`services/sale_service.py:536`, `services/purchase_service.py:269`) into the
   same `DECIMAL(10,3)` columns — TEXT in some rows, REAL in others.
4. **The CI drift check is names-only and one-directional**, so all of the above
   ships silently; and **no CI leg ever tests upgrading a legacy-shaped DB**.

## Current state

- `database/__init__.py:77-89` — `_load_table_statements` returns only statements
  whose stripped text starts with `CREATE TABLE` (the index block is dropped).
- `schema.sql:115-127` — 10 `CREATE INDEX IF NOT EXISTS` statements (dead).
- `alembic/versions/e318e5c02e34_initial_schema.py:124-159` — 15 `CREATE INDEX
  IF NOT EXISTS` statements (live source of indexes on legacy DBs; also runs on
  fresh DBs after schema.sql).
- `schema.sql:55` — `receipt_id TEXT UNIQUE` (implicit unique index) AND the
  migration creates `idx_sales_receipt_id ... UNIQUE` — a duplicate unique index.
- `services/sale_service.py:532-550` (`_insert_sale_items` writes
  `str(round(float(item["quantity"]), 3))`), `services/purchase_service.py:262-273`
  (same pattern).
- `scripts/check_schema_drift.py:41-78` — compares table/column NAMES only, one
  direction (`metadata - db`), via `PRAGMA table_info`.
- `.github/workflows/ci.yml:43-46` — drift check step: `python scripts/check_schema_drift.py`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Drift check | `.venv/bin/python scripts/check_schema_drift.py` | Schema drift check passed |
| Index dump | `.venv/bin/python -c "import sqlite3; c=sqlite3.connect('billing_inventory.db'); print([r for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sale_items'\")])"` | the current dup set (record it) |
| Query plan | `.venv/bin/python -c "import sqlite3; c=sqlite3.connect('billing_inventory.db'); print(list(c.execute('EXPLAIN QUERY PLAN SELECT * FROM sale_items WHERE sale_id=1')))"` | shows which index the planner picks |
| Tests | `.venv/bin/python -m pytest tests/test_database tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `schema.sql` — remove the dead index block (indexes become migration-owned)
- `alembic/versions/` — ONE new revision (cleanup: drop duplicates + stale index + quantity-type normalization); do not edit `e318e5c02e34_initial_schema.py`
- `services/sale_service.py:532-550`, `services/purchase_service.py:262-273` — numeric quantity storage
- `scripts/check_schema_drift.py` — index-set + both-direction comparison
- `scripts/check_legacy_upgrade.py` — NEW (legacy-DB upgrade test)
- `.github/workflows/ci.yml` — legacy-upgrade step
- `tests/test_database/` — migration + quantity-type tests
- `AGENTS.md` — one line if the schema-source contract changes (indexes are migration-owned)

**Out of scope**:
- `models/*.py` — no model changes in this plan
- `ui/*`, `services/` other than the two quantity writes — no behavior changes
- The PERF-09 audit-index suggestion (`idx_audit_log_entity_timestamp`) — add it ONLY if the new index-set drift check flags it; otherwise leave for a follow-up
- Dropping the implicit `receipt_id` UNIQUE — keep it; only the explicit duplicate index goes

## Git workflow

- Branch: `advisor/004-index-migration`
- Commit messages: `fix(schema): apply indexes via migration only`, `feat(db): cleanup migration dropping duplicate and stale indexes`, `fix: store item quantities as numbers consistently`, `test: extend schema drift check to index sets`, `test: legacy database upgrade path`
- Do NOT push unless instructed.

## Steps

### Step 1: Record the current index state (baseline)

Dump `PRAGMA index_list(<table>)` + `index_info` for `sales`, `sale_items`,
`purchase_items`, `inventory`, `products`, `customers`, `categories`,
`purchase_items` from the real `billing_inventory.db` AND from a fresh
`init_db()` scratch DB (use `DATABASE_NAME=scratch.db`). Save both dumps in
your report. This is the ground truth the cleanup revision is written against.

**Verify**: both dumps recorded; they differ (that difference is the bug).

### Step 2: Delete the dead index block from schema.sql

Remove lines `schema.sql:115-127` (the `CREATE INDEX IF NOT EXISTS` block after
the table definitions). Add a comment line where the block was:
`-- Indexes are owned by alembic/versions/*; schema.sql defines tables only.`

**Verify**: `.venv/bin/python scripts/check_schema_drift.py` still passes (the
drift check does not compare indexes yet; table/column names unchanged).

### Step 3: Write the cleanup migration

Create ONE new revision (run `alembic revision -m "cleanup: deduplicate indexes and normalize quantity types"`
from the repo root with the venv active — `alembic` console script works now;
if it does not, use `.venv/bin/python -m alembic revision ...`). It must be
idempotent (safe on fresh AND legacy DBs). Content:

1. `DROP INDEX IF EXISTS` for exact duplicates and the stale index, guided by
   your Step 1 dump, per this decision table (keep the FIRST of each pair):
   - `sale_items`: drop `idx_sale_items_sale_id` (keep `idx_sale_items_sale`),
     drop `idx_sale_items_sale_product` (keep `idx_sale_items_composite`)
   - `purchase_items`: drop `idx_purchase_items_sale_id`-equivalent single-col
     duplicate if present (keep the composite `idx_purchase_items_purchase_product`),
     drop any single-column duplicate of it
   - `sales`: drop `idx_sales_customer_id` (keep `idx_sales_customer`), drop
     `idx_sales_date_customer` (keep `idx_sales_customer_date`), drop
     `idx_sales_receipt` (keep `idx_sales_receipt_id`; the table's implicit
     UNIQUE on `receipt_id` remains)
   - `inventory`: drop `idx_inventory_product_id` (keep `idx_inventory_product`)
   - `categories`: drop `idx_categories_parent_id` (stale — no such column)
   - If your Step 1 dump shows a pair the table above doesn't name, apply the
     rule "identical definition, different name → drop one" and note it.
   - If the dump shows something the table contradicts (e.g., a kept index is
     missing), STOP and report.
2. Before dropping, run `EXPLAIN QUERY PLAN` on the queries in
   `services/sale_service.py:208-217` (sales by date range), `:490-500`
   (items by sale), `ui/sale_view.py`'s sales query, and
   `services/purchase_query_service.py:245-276` — confirm the KEPT indexes are
   the ones the planner uses. Record plans before/after in the report.
3. Quantity normalization (TEXT → REAL) in the same revision:
   ```sql
   UPDATE sale_items SET quantity = CAST(quantity AS REAL) WHERE typeof(quantity) = 'text';
   UPDATE purchase_items SET quantity = CAST(quantity AS REAL) WHERE typeof(quantity) = 'text';
   ```

**Verify**: `.venv/bin/python -m pytest tests/test_database -q` → all pass;
`.venv/bin/python scripts/check_schema_drift.py` → passed; on the real DB copy
(back it up first: `cp billing_inventory.db /tmp/opencode/db-test-copy.db` and
run alembic against the copy via `DATABASE_NAME`), `PRAGMA index_list` shows the
kept set and `SELECT typeof(quantity) FROM sale_items GROUP BY typeof(quantity)`
shows no `text` rows.

### Step 4: Numeric quantity writes

In `services/sale_service.py:532-550` (`_insert_sale_items`) and
`services/purchase_service.py:262-273` (`_insert_purchase_items`), replace
`str(round(float(item["quantity"]), QUANTITY_PRECISION))` with
`round(float(item["quantity"]), QUANTITY_PRECISION)` (numeric value).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py -q` → all pass.

### Step 5: Extend the drift check

In `scripts/check_schema_drift.py`:

- Compare in BOTH directions for columns (flag `db - metadata` extras too).
- Add index-set comparison: define the CANONICAL index list (the kept set from
  Step 3) as a module constant `CANONICAL_INDEXES: dict[str, set[str]]`
  (table → index names); compare against `PRAGMA index_list` of the fresh
  `init_db()` DB; flag missing or extra entries. Exclude the auto-created
  `sqlite_autoindex_*` and `ix_*` SQLModel-generated indexes (list them in an
  exclusion set, do not silently ignore).
- Keep the type comparison OUT (SQLite affinity noise — see plan 014's notes;
  the drift check stays names+indexes).

**Verify**: `.venv/bin/python scripts/check_schema_drift.py` → passed; then
temporarily add an extra `CREATE INDEX` to the migration, re-run → FAILS with a
clear message, then revert (this proves the check has teeth).

### Step 6: Legacy-DB upgrade test

Create `scripts/check_legacy_upgrade.py` that:

1. Builds a "legacy" DB by parsing `schema.sql` and stripping the migration-added
   columns (hardcode this strip list: `categories.created_at/updated_at`,
   `products.is_active/deleted_at/created_at/updated_at`,
   `inventory.created_at/updated_at`, `customers.is_active/deleted_at`,
   `sales.status/created_at`, `sale_items.created_at`, `purchases.created_at`)
   — mechanical line removal per CREATE TABLE block; if any strip column is not
   found, print a warning but continue.
2. Runs `init_db()` on it (set `DATABASE_NAME` env like the drift script does).
3. Asserts: every stripped column now exists; the canonical index set exists;
   quantity columns contain no `text` values.

Add a CI step in `.github/workflows/ci.yml` after the drift-check step:
`python scripts/check_legacy_upgrade.py`.

**Verify**: `.venv/bin/python scripts/check_legacy_upgrade.py` → exit 0 with
"Legacy upgrade check passed".

## Test plan

- `tests/test_database/` — one test asserting the cleanup revision is
  idempotent (run `alembic upgrade head` twice on a scratch DB; second run is a
  no-op). Pattern: `tests/test_database/test_init_db.py`.
- One test asserting mixed-type quantities from the update path store numeric
  values: create a sale via the UPDATE workflow path (the `update_sale` public
  entry), then `SELECT typeof(quantity)` → `real`.
- The legacy-upgrade script is CI-verified (not a pytest test).

## Done criteria

- [ ] `.venv/bin/python scripts/check_schema_drift.py` passes AND fails when a migration adds an unexpected index (proven, then reverted)
- [ ] `.venv/bin/python scripts/check_legacy_upgrade.py` exits 0
- [ ] New alembic revision exists under `alembic/versions/`; `e318e5c02e34_initial_schema.py` untouched (`git status`)
- [ ] Real-DB-copy `PRAGMA index_list` shows the kept set; no identical-definition duplicates remain
- [ ] `grep -rn "str(round(float" services/` → no matches
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] No files outside the in-scope list are modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- The Step 1 dump contradicts the decision table (a kept index is absent, or an
  unexpected duplicate exists) — STOP and report the actual index state.
- `EXPLAIN QUERY PLAN` shows a to-be-dropped index is the planner's only option
  for a hot query — STOP and report; do not drop it.
- `alembic revision` scaffolding fails (env/config) — report; do not hand-write
  revision files from memory.
- The legacy script's column-strip logic produces a DB that fails `init_db()`
  with unrelated errors — STOP and report the failing table.

## Maintenance notes

- Index contract after this plan: **indexes live in Alembic revisions only**;
  schema.sql is tables-only; the drift check enforces it.
- When models add `index=True`/`unique=True` (SQLModel auto-indexes), the drift
  check's exclusion set must be revisited — those `ix_*` indexes are metadata-owned.
- The quantity-type normalization is a one-way data change; old backups restore
  TEXT values that the next `init_db()` migration re-normalizes (the UPDATE is
  idempotent).
- Reviewer: confirm the migration is safe to run twice and on the operator's
  real DB (test on a copy first — the plan says so).
