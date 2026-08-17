# Plan 038: Introduce SaleStatus enum; bind status in SQL to enum values

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- models/enums.py models/sale.py services/sale_service.py services/update_sale_workflow.py services/inventory_service.py services/analytics/metrics.py schema.sql`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

Sale status is a stringly-typed literal scattered across ~20 sites. The model
has no `SaleStatus` enum (only `StockMovementType` and `InventoryAction` in
`models/enums.py`). Plan 015's "exclude cancelled sales from reports" change
required hand-editing every `status = 'confirmed'` predicate in lockstep, and a
typo in one WHERE clause silently includes/excludes data. The Python-side
comparisons (`sale.status == "cancelled"`) are likewise untyped. This plan adds
a `SaleStatus` enum, uses it for Python comparisons and model defaults, and
binds the status in SQL WHERE clauses as a parameter (bandit-clean, single
source of truth), so a future status change is a one-line edit per query
instead of a blind 20-site sweep.

## Current state

`models/enums.py` (full file, 26 lines) has `StockMovementType`,
`InventoryAction`, `TimeInterval`, and the constants `QUANTITY_PRECISION`,
`MAX_PRICE_CLP`, `MAX_SALE_ITEMS`, `MAX_PURCHASE_ITEMS`. No sale status.

Literal sites (grep-verified at commit `d560e43`):

- Python comparisons / writes:
  - `services/sale_service.py:256,304` — `if sale.status == "cancelled":`
  - `services/sale_service.py:315` — `"UPDATE sales SET status = 'cancelled' WHERE id = ?"`
  - `services/update_sale_workflow.py:40` — `if sale.status == "cancelled":`
  - `models/sale.py:138` — `VALID_STATUSES = frozenset({"confirmed", "cancelled"})`
  - `models/sale.py:174-179` — `status: str = Field(default="confirmed", ... server_default=sa.text("'confirmed'"))`
  - `models/sale.py:256-260` — `validate_status(status)` compares against `VALID_STATUSES`
- SQL predicates:
  - `services/sale_service.py:357,381,404,619` — `status = 'confirmed'` / `s.status = 'confirmed'`
  - `services/analytics/metrics.py:33,74,118,193,238,277,310,358,419,470` — `status = 'confirmed'` / `s.status = 'confirmed'`
  - `services/inventory_service.py:353,388` — `s.status = 'confirmed'`
- Schema:
  - `schema.sql:58` — `status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled'))`
  - `models/sale.py:147-149` — `CheckConstraint("status IN ('confirmed', 'cancelled')", name="check_sale_status")`

**Repo conventions**:
- Constants live in `models/enums.py` (AGENTS.md: "Do not change constants in
  models/enums.py without auditing validators, schema assumptions, and affected
  tests").
- SQL is parameterized; bandit runs with `--skip B101` and only `# nosec B608`
  on parameterized string-built queries (no bare nosec).
- Both `schema.sql` and the SQLModel metadata must stay in sync
  (`scripts/check_schema_drift.py` gates CI).

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Sale service tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_update_sale_workflow.py` | all pass |
| Analytics tests | `.venv/bin/python -m pytest tests/analytics/ tests/test_services/test_analytics_service.py` | all pass |
| Inventory tests | `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` | all pass |
| Model tests | `.venv/bin/python -m pytest tests/test_models/` | all pass |
| Schema drift | `.venv/bin/python scripts/check_schema_drift.py` | exit 0, no drift |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Security | `.venv/bin/bandit -q -r database services utils --skip B101` | exit 0 |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `models/enums.py`
- `models/sale.py`
- `services/sale_service.py`
- `services/update_sale_workflow.py`
- `services/inventory_service.py`
- `services/analytics/metrics.py`
- `schema.sql`
- `tests/` (only to fix assertions that pin status strings)

**Out of scope**:
- `models/purchase.py` and purchase status (purchases have no status column)
- Any change to the CHECK constraint's allowed values (only its construction changes)
- Analytics metric structure consolidation (plan 048)

## Git workflow

- Branch: `advisor/038-sale-status-enum`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add the SaleStatus enum

In `models/enums.py`, after `TimeInterval`, add:

```python
class SaleStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
```

**Verify**: `.venv/bin/python -c "from models.enums import SaleStatus; print(SaleStatus.CONFIRMED.value, SaleStatus.CANCELLED.value)"` → `confirmed cancelled`.

### Step 2: Update the Sale model

In `models/sale.py`:
- Import: `from models.enums import SaleStatus`.
- Replace `VALID_STATUSES = frozenset({"confirmed", "cancelled"})` (:138) with
  `VALID_STATUSES = frozenset(status.value for status in SaleStatus)`.
- Change the `status` field (:174-179) default to
  `default=SaleStatus.CONFIRMED.value` and the server_default to
  `sa.text(f"'{SaleStatus.CONFIRMED.value}'")`.
- Build the CHECK constraint (:147-149) from the enum:
  `sa.CheckConstraint(f"status IN ({', '.join(repr(s.value) for s in SaleStatus)})", name="check_sale_status")`
  — this must render exactly `status IN ('confirmed', 'cancelled')`; verify
  with a print before committing.
- Update `validate_status` (:256-260) to compare against `VALID_STATUSES`
  (already does) — it can now also accept enum members transparently
  (StrEnum == its value), so no body change needed beyond the constant.

**Verify**: `.venv/bin/python -c "from models.sale import Sale, VALID_STATUSES; print(sorted(VALID_STATUSES))"` → `['cancelled', 'confirmed']`.
`grep -n "check_sale_status" models/sale.py` shows the constraint built from `SaleStatus`.

### Step 3: Update Python-side comparisons

In `services/sale_service.py`:
- Import `SaleStatus` from `models.enums`.
- `:256` and `:304`: `if sale.status == SaleStatus.CANCELLED:`
- `:315`: keep the UPDATE literal `'cancelled'` OR bind it: prefer keeping the
  SQL literal here (it is a write, not a predicate) but write it as
  `f"... SET status = '{SaleStatus.CANCELLED.value}' ..."` is NOT allowed
  (string-built SQL without nosec). Keep the plain literal and add a trailing
  comment `# SaleStatus.CANCELLED`.
- `:357,381,404,619`: convert the predicate to a bound parameter:
  `... AND status = ?` / `... AND s.status = ?` and append
  `SaleStatus.CONFIRMED.value` to the query's parameter tuple in the SAME
  position order (params tuple currently is `(start_date, end_date)` → becomes
  `(start_date, end_date, SaleStatus.CONFIRMED.value)`).

In `services/update_sale_workflow.py`:
- Import `SaleStatus`; `:40` → `if sale.status == SaleStatus.CANCELLED:`.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_update_sale_workflow.py` → all pass.

### Step 4: Update the analytics and inventory predicates

In `services/analytics/metrics.py`:
- Import `SaleStatus` from `models.enums`.
- For each of the 10 sites (:33,74,118,193,238,277,310,358,419,470):
  - Replace `status = 'confirmed'` / `s.status = 'confirmed'` with
    `status = ?` / `s.status = ?`.
  - Append `SaleStatus.CONFIRMED.value` to the query's parameter tuple.
    CAREFUL: the param tuples in `get_parameters` must match the new
    placeholder count and order. Note `:193` is a JOIN ON condition
    (`LEFT JOIN sales s ON si.sale_id = s.id AND s.status = 'confirmed'`) — it
    uses the same `(start_date, end_date)` params as the metric's main query, so
    appending the status param works the same way.
- Run the analytics test suite after EACH file edit (they assert row counts
  and values, so a param-order mistake will fail loudly).

In `services/inventory_service.py`:
- Import `SaleStatus`; `:353` and `:388` → `s.status = ?`, appending
  `SaleStatus.CONFIRMED.value` to the params tuple (`:362` builds
  `(product_id, start_date, end_date) * 3` — append the value once per arm;
  verify against the actual placeholder order).

**Verify**: `.venv/bin/python -m pytest tests/analytics/ tests/test_services/test_analytics_service.py tests/test_services/test_inventory_service.py` → all pass.

### Step 5: Align schema.sql and run drift + security checks

`schema.sql:58` already matches the enum values (`'confirmed'`, `'cancelled'`);
no literal change needed. Confirm the SQLModel metadata constraint renders the
same text (Step 2 verification).

**Verify**:
- `.venv/bin/python scripts/check_schema_drift.py` → exit 0.
- `.venv/bin/bandit -q -r database services utils --skip B101` → exit 0.
- `grep -rn "\"cancelled\"\|\"confirmed\"" services/ --include="*.py"` → only
  remaining bare literals are the comment-annotated write at
  `sale_service.py:315` (and any you deliberately kept).

### Step 6: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Existing tests already cover the status behavior (cancelled exclusion in
  reports, cancel/delete guards). Run the full targeted suites listed above.
- Add one test in `tests/test_models/` asserting `VALID_STATUSES` equals
  `{s.value for s in SaleStatus}` (guards future enum/constant drift).
- If any test asserted a status string literal, update it to the enum value.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `.venv/bin/python scripts/check_schema_drift.py` exits 0
- [ ] `.venv/bin/bandit -q -r database services utils --skip B101` exits 0
- [ ] `grep -n "status == \"cancelled\"\|status == \"confirmed\"" services/ models/` returns no matches
- [ ] `grep -rn "status = 'confirmed'\|status = 'cancelled'\|s.status = 'confirmed'" services/` returns no matches (all bound as `?` params)
- [ ] `VALID_STATUSES` test exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A metrics test fails after a param-order change and the fix is not obvious
  (report the failing query and the metric class).
- `scripts/check_schema_drift.py` reports drift that is not caused by this
  plan's own edits (pre-existing drift — report, do not fix blindly).
- The CHECK constraint text no longer renders `status IN ('confirmed', 'cancelled')`.
- `sale.status` is ever assigned a non-str type in production code that would
  break a str-only comparison (search `status=` on Sale objects).

## Maintenance notes

- The single source of truth for sale status is now `SaleStatus` in
  `models/enums.py`. New statuses (e.g. `refunded`) require: one enum member,
  one CHECK/constraint update, and — because SQL predicates are now bound — no
  query-literal sweep.
- The metrics consolidation plan (048) will centralize the date-range WHERE
  predicate; keep the bound-status pattern it establishes.
- Reviewer should verify cancelled-sale exclusion still holds for every report
  (the exact behavior plan 015 pinned).