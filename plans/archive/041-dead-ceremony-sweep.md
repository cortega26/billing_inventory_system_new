# Plan 041: Dead-ceremony sweep — exceptions, enums, calculator constant, main.py dicts

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- utils/exceptions.py models/enums.py utils/math/financial_calculator.py main.py models/inventory.py services/inventory_service.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

Four unrelated pieces of dead ceremony mislead readers and carry drift risk:
(1) an 11-class exception taxonomy where the classes are never raised (only
`ValidationException`, `DatabaseException`, `NotFoundException`,
`ConfigurationException`, `UIException` are used in production); (2) a
`StockMovementType` enum and an `InventoryAction.SET` member that no code
participates in; (3) `FinancialCalculator` redefining `QUANTITY_PRECISION`
(with a comment admitting the duplication) plus two unused methods; (4)
`main.py` keeping two identical dicts of count queries for the same 8 tables.
All deletions below are zero-reference-guarded per the repo's dead-code rule
(plan 011).

## Current state

Verified at commit `d560e43`:

1. `utils/exceptions.py` — 17 classes. Production references (grep, excluding
   the definitions file, `tests/`, `.venv`):
   - Used: `DatabaseException`, `ValidationException`, `NotFoundException`,
     `ConfigurationException` (3 refs), `UIException` (81 refs), `AppException`.
   - UNUSED (0 production refs): `BusinessLogicException`, `NetworkException`,
     `SecurityException`, `ExternalServiceException`, `FileOperationException`,
     `AuthenticationException`, `AuthorizationException`, `DataFormatException`,
     `SystemConfigurationException`, `ResourceException`, `ConcurrencyException`.
   - `AppException.__init__` accepts `error_code`/`details` but no production
     caller sets them (only `tests/test_system/test_exceptions.py`).
2. `models/enums.py:4-7` — `StockMovementType` (SALE/PURCHASE/ADJUSTMENT): zero
   references outside the definition.
3. `models/enums.py:13` — `InventoryAction.SET`: zero references (only CREATE
   and UPDATE are passed to `InventoryService._modify_inventory`).
4. `utils/math/financial_calculator.py:11-13` —
   `QUANTITY_PRECISION = 3` with comment "matching models.enums.QUANTITY_PRECISION";
   `round_quantity` (:83-87) and `calculate_sale_totals` (:55-80) have only
   test callers (`tests/test_utils/test_financial_calculator.py`;
   `tests/test_services/test_sale_service.py:156` uses `calculate_sale_totals`).
5. `main.py:29-49` — `TABLE_COUNT_QUERIES` (`SELECT COUNT(*) AS count FROM x`)
   and `TABLE_TOTAL_QUERIES` (`SELECT COUNT(*) FROM x`) for the same 8 tables;
   consumers: `_get_primary_table_counts` (:55, reads `row["count"]`) and
   `_count_records_in_database_file` (:67, reads `cursor.fetchone()[0]`).

**Repo conventions**:
- Dead-code deletions use the zero-reference guard: definition + zero other
  hits across the repo (tests excluded only when classified test-only). Every
  deleted symbol must have its caller(s) removed or updated in the same change.
- Constants have a single source of truth in `models/enums.py`.
- No bare `# nosec`; bandit must stay clean.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Exceptions tests | `.venv/bin/python -m pytest tests/test_system/test_exceptions.py` | all pass (after update) |
| Financial calc tests | `.venv/bin/python -m pytest tests/test_utils/test_financial_calculator.py tests/test_services/test_sale_service.py` | all pass (after update) |
| Inventory tests | `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py tests/test_ui/test_inventory_view.py` | all pass |
| Startup guard tests | `.venv/bin/python -m pytest tests/test_startup_guard.py tests/test_smoke.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Security | `.venv/bin/bandit -q -r database services utils --skip B101` | exit 0 |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `utils/exceptions.py`
- `models/enums.py`
- `utils/math/financial_calculator.py`
- `main.py`
- `services/inventory_service.py` (only to delete the `InventoryAction.SET`
  handling if the `else: raise ValueError` branch is removed — otherwise not touched)
- `tests/test_system/test_exceptions.py`
- `tests/test_utils/test_financial_calculator.py`
- `tests/test_services/test_sale_service.py` (only the `test_calculate_sale_totals` test)
- `tests/test_startup_guard.py` / `tests/test_smoke.py` (if they reference the merged dicts)

**Out of scope**:
- `utils/exceptions.py` `AppException.__init__` signature (keep `error_code`/
  `details`; they are used by tests and harmless)
- `models/inventory.py` `StockStatus` (used by `Inventory.get_stock_status`)
- Anything else not listed above

## Git workflow

- Branch: `advisor/041-dead-ceremony-sweep`
- Commit per logical unit (one commit per subsystem: exceptions, enums,
  calculator, main.py).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Trim the exception taxonomy

In `utils/exceptions.py`, delete the 11 unused leaf classes listed in
"Current state" #1. Keep: `AppException`, `DatabaseException`,
`ValidationException`, `ConfigurationException`, `UIException`,
`NotFoundException`.

In `tests/test_system/test_exceptions.py`, update/remove assertions that
reference the deleted classes (they exist to pin the taxonomy).

**Verify**: for each deleted name, `grep -rn "<Name>" --include="*.py" . | grep -v .venv`
→ matches only `tests/test_system/test_exceptions.py` if any (report them as
updated); then `.venv/bin/python -m pytest tests/test_system/test_exceptions.py` → pass.

### Step 2: Remove StockMovementType and InventoryAction.SET

In `models/enums.py`: delete the `StockMovementType` class (:4-7) and the
`SET = "set"` member (:13) from `InventoryAction`.
In `services/inventory_service.py`: `_modify_inventory` (:144-160) branches on
UPDATE/CREATE with a defensive `else: raise ValueError` for the third state.
Keep the `else` as-is (defensive) OR delete it — your choice, but if you delete
it, keep the UPDATE/CREATE branches identical.

**Verify**: `grep -rn "StockMovementType" --include="*.py" .` → only matches in
`tests/` if any (update them). `grep -rn "InventoryAction.SET" --include="*.py" .`
→ no matches.

### Step 3: Fix the calculator constant and drop unused methods

In `utils/math/financial_calculator.py`:
- Delete the local `QUANTITY_PRECISION = 3` (:13) and its comment.
- Add `from models.enums import QUANTITY_PRECISION` at the top. **Check for a
  circular import**: `models/enums.py` imports nothing from `utils/`, so this
  is safe (verify with `.venv/bin/python -c "import utils.math.financial_calculator"`).
- Delete `calculate_sale_totals` (:55-80) and `round_quantity` (:83-87).
- In `tests/test_services/test_sale_service.py`, delete
  `test_calculate_sale_totals` (:156) — it pins the removed method.
- In `tests/test_utils/test_financial_calculator.py`, delete/update tests that
  call `round_quantity` or `calculate_sale_totals`.

**Verify**: `.venv/bin/python -c "import utils.math.financial_calculator"` → exit 0.
`grep -rn "round_quantity\|calculate_sale_totals" --include="*.py" .` → no
matches outside deleted test lines. `.venv/bin/python -m pytest tests/test_utils/test_financial_calculator.py tests/test_services/test_sale_service.py` → pass.

### Step 4: Merge the main.py query dicts

In `main.py`, replace `TABLE_COUNT_QUERIES` and `TABLE_TOTAL_QUERIES` with a
single dict using the aliased query (both consumers work with it):

```python
TABLE_COUNT_QUERIES = {
    "customers": "SELECT COUNT(*) AS count FROM customers",
    # ... same 8 tables, aliased form ...
}
```

Update `_count_records_in_database_file` (:60-73) to use `TABLE_COUNT_QUERIES`
and read `cursor.fetchone()[0]` (or `row["count"]`), and delete the now-empty
`TABLE_TOTAL_QUERIES`.

**Verify**: `grep -n "TABLE_TOTAL_QUERIES" main.py` → no matches.
`.venv/bin/python -m pytest tests/test_startup_guard.py tests/test_smoke.py` → pass.

### Step 5: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/bandit -q -r database services utils --skip B101`
→ exit 0; `.venv/bin/ruff check .` → exit 0; `.venv/bin/black --check .` → exit 0;
`.venv/bin/pyright` → exit 0.

## Test plan

- Update `tests/test_system/test_exceptions.py` (remove deleted classes).
- Update `tests/test_utils/test_financial_calculator.py` and
  `tests/test_services/test_sale_service.py` (remove deleted-method tests).
- Existing inventory/config/startup tests cover the rest; no new behavior
  tests needed (pure deletion).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "BusinessLogicException\|NetworkException\|SecurityException\|ExternalServiceException\|FileOperationException\|AuthenticationException\|AuthorizationException\|DataFormatException\|SystemConfigurationException\|ResourceException\|ConcurrencyException" --include="*.py" .` returns no matches
- [ ] `grep -rn "StockMovementType\|InventoryAction.SET" --include="*.py" .` returns no matches
- [ ] `grep -n "QUANTITY_PRECISION" utils/math/financial_calculator.py` shows an import, not a local assignment
- [ ] `grep -n "TABLE_TOTAL_QUERIES" main.py` returns no matches
- [ ] `.venv/bin/bandit -q -r database services utils --skip B101` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- Any "unused" symbol has a production caller you discover during the sweep
  (the grep counts above were run at plan time; if a new caller exists, it is
  drift — report instead of deleting).
- Importing `QUANTITY_PRECISION` into `financial_calculator.py` causes a
  circular import (report — there is an alternate arrangement via a
  `utils/constants.py` module that the reviewer can approve).
- A startup-guard test depends on the two-dict structure.

## Maintenance notes

- The exception hierarchy is now 6 classes. New exception types should be added
  only when a caller needs them; `AppException.__init__` keeps `error_code`/
  `details` for test/back-compat.
- `QUANTITY_PRECISION` and `MAX_PRICE_CLP` now have exactly one source
  (`models/enums.py`) — this is the invariant the AGENTS.md constant rule
  protects.
- `main.py`'s count queries are now one dict; the startup guard's behavior is
  unchanged.