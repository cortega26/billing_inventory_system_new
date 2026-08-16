# Plan 031: `get_inventory_movements` must see same-day adjustments (local-time stamps + range-shift)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> Touch only the files listed as in scope. If any STOP condition occurs, stop
> and report — do not improvise. When done, update the status row for this
> plan in `plans/README.md` — unless a reviewer dispatched you and told you
> they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 0b99aa5..HEAD -- services/inventory_service.py tests/test_services/test_inventory_service.py schema.sql`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2 (backlog bug)
- **Effort**: S
- **Risk**: LOW-MED (date semantics change on the movement ledger; going forward only)
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `0b99aa5`, 2026-08-16

## Why this matters

The movement ledger ("Virtual Ledger", `get_inventory_movements`) silently
misses manual adjustments made late in the day. Two compounding causes
(backlog item, surfaced by plan 018):

1. Adjustment rows are stamped `CURRENT_TIMESTAMP` — **UTC**. On any machine
   west of UTC (e.g. UTC-4), a 23:00 local adjustment is stored as
   "tomorrow" 03:00 UTC.
2. All three union arms filter with date-only `BETWEEN ? AND ?`, so a row
   dated "tomorrow" is outside today's range.

Result: a stock count done at 22:00 does not appear in today's movement
history — exactly when reconciliations happen. The fix mirrors plan 019:
store LOCAL time at the write sites and range-shift the query arms so
`CURRENT_TIMESTAMP`-style rows on the end date are included.

## Current state

```python
# services/inventory_service.py:232-235 (set_quantity) and :309-312 (adjust_inventory)
DatabaseManager.execute_query(
    "INSERT INTO inventory_adjustments (product_id, quantity_change, reason, date) "
    "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
    (product_id, quantity_change, "manual set"),  # or reason
)

# services/inventory_service.py:351-368 (get_inventory_movements)
query = """
    SELECT 'adjustment' as type, date, quantity_change, reason
    FROM inventory_adjustments
    WHERE product_id = ? AND date BETWEEN ? AND ?
    UNION ALL
    SELECT 'sale' as type, s.date, -si.quantity as quantity_change, 'Sale' as reason
    FROM sale_items si
    JOIN sales s ON si.sale_id = s.id
    WHERE si.product_id = ? AND s.date BETWEEN ? AND ?
    UNION ALL
    SELECT 'purchase' as type, p.date, pi.quantity as quantity_change, 'Purchase' as reason
    FROM purchase_items pi
    JOIN purchases p ON pi.purchase_id = p.id
    WHERE pi.product_id = ? AND p.date BETWEEN ? AND ?
    ORDER BY date
"""
params = (product_id, start_date, end_date) * 3
```

The plan-018 regression test
(`tests/test_services/test_inventory_service.py::test_ui_manual_edit_path_writes_movement_and_audit_rows`)
currently backdates the row via a SQL UPDATE with a comment explaining this
bug — after this fix the workaround can be replaced by a same-day range.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `services/inventory_service.py` — the two INSERT statements + the three
  union-arm predicates in `get_inventory_movements`
- `tests/test_services/test_inventory_service.py` — fix the backdate
  workaround; add a same-day regression test
- `schema.sql` — verify the `customers` DDL carries the name-length CHECK
  (`CHECK (name IS NULL OR LENGTH(name) <= 50)`); if absent, add it in the
  same change (backlog reconciliation; the model + live DB already have it)

**Out of scope** (do NOT touch):
- Historical rows already stored in UTC — they keep their stored value
  (documented; only the query bounds change, which is the best that can be
  done without rewriting history)
- `get_inventory_turnover`, analytics, or any other date logic
- The `sale_items`/`purchases` arms' semantics beyond the predicate form

## Git workflow

- Branch: `advisor/031-movements-local-time`
- Commit per logical unit; message style follows the repo (`fix: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Local-time stamps at the write sites

In `services/inventory_service.py`, both INSERTs (set_quantity and
adjust_inventory) change the date expression:

```python
"VALUES (?, ?, ?, datetime('now', 'localtime'))"
```

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` → passes (existing adjustment tests still green).

### Step 2: Range-shift the three union arms

In `get_inventory_movements`, replace every `BETWEEN ? AND ?` arm predicate
with the plan-019 form (end date inclusive for timestamped rows):

- adjustment arm: `WHERE product_id = ? AND date >= ? AND date < date(?, '+1 day')`
- sale arm: `WHERE si.product_id = ? AND s.date >= ? AND s.date < date(?, '+1 day')`
- purchase arm: `WHERE pi.product_id = ? AND p.date >= ? AND p.date < date(?, '+1 day')`

`params = (product_id, start_date, end_date) * 3` stays unchanged.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` → passes.

### Step 3: Fix the backdate workaround + regression test

1. In `tests/test_services/test_inventory_service.py::test_ui_manual_edit_path_writes_movement_and_audit_rows`,
   remove the SQL-UPDATE backdate workaround and query the range ending today
   instead (the row is now stamped local time and included by the shifted
   bound):
   - `adjust_inventory(self.prod_id, 5.0, "manual set")`
   - `movements = self.inventory_service.get_inventory_movements(self.prod_id, "2000-01-01", <today ISO>)`
   - assert the adjustment row appears with `reason == "manual set"`.
   (Keep the rest of the test — quantity + ledger row assertions.)
2. Add `test_movements_include_late_day_adjustment` — the exact scenario from
   the backlog: adjust now, query today's range, assert the row appears
   (pre-fix this failed on UTC+ offset machines). Both tests must pass in any
   timezone.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py -k "manual_edit or late_day"` → 3 passed (the two Step-3 tests + the negative-path test).

### Step 4: schema.sql name-CHECK reconciliation

Check `schema.sql`'s `customers` DDL for
`CHECK (name IS NULL OR LENGTH(name) <= 50)`. If absent (the model at
`models/customer.py:29-31` and the live DB both have it), add it to
`schema.sql` in the same commit. If present, no change.

**Verify**: `rg -n "LENGTH(name)" schema.sql models/customer.py` → both present; `.venv/bin/python scripts/check_schema_drift.py` → exit 0.

### Step 5: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass (modulo pre-existing worktree UI
  exceptions: 7 in `tests/test_ui/test_main_window_helpers.py`, 4 backup tests)
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean
- `.venv/bin/python scripts/check_schema_drift.py` → exit 0

## Test plan

| Test | File | Case |
|------|------|------|
| same-day adjustment visible | test_inventory_service.py (new `late_day`) | adjust now → appears in today's range (any timezone) |
| manual-edit movement test | test_inventory_service.py (updated) | backdate workaround removed; today-range query |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `rg -n "CURRENT_TIMESTAMP" services/inventory_service.py` → no matches (both writes use `datetime('now','localtime')`)
- [ ] `rg -n "BETWEEN \? AND \?" services/inventory_service.py` → no matches in `get_inventory_movements` (all three arms range-shifted)
- [ ] The backdate SQL-UPDATE is gone from `test_ui_manual_edit_path_writes_movement_and_audit_rows`
- [ ] `schema.sql` carries the name-length CHECK (or was already present — verified)
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- A same-day test fails on this machine AND the failure looks timezone-related
  (report the observed stamps — don't paper over it).
- `schema.sql`'s customers DDL structure differs from the excerpt.
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- Historical UTC-stamped adjustment rows remain UTC in storage; the shifted
  bounds make late-day rows visible going forward. A full backfill (rewriting
  old rows to localtime) is deliberately out of scope.
- The plan-018 test's backdate workaround was the canary for this bug — if
  it ever needs reintroducing, the bug is back.
- Reviewer scrutiny: the two write sites, the three arms, and that
  `get_inventory_turnover` was untouched.
