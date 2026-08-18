# Plan 050: Remove low-stock inventory reporting that duplicates the analytics domain

> **AMENDMENT 2026-08-17 (executor STOP → plan defect)**: the original plan's
> claim that `get_inventory_turnover`'s only test is a `pass` stub was FALSE —
> `tests/test_services/test_inventory_service.py:286-305,329-348` has two real
> asserting tests (`test_get_inventory_turnover`, `test_turnover_excludes_cancelled_sales`).
> REVISED SCOPE: KEEP `get_inventory_turnover` (tested, working, pins the
> cancelled-exclusion contract; deleting it would remove test-pinned behavior).
> Delete ONLY `get_low_stock_products`; delete its test `test_low_stock_threshold`
> from `tests/test_services/test_ux_features.py` (its threshold coverage is
> duplicated by `test_get_low_stock_wrapper` + `test_manual_inventory_mutations_clear_analytics_low_stock_cache`
> in `tests/test_services/test_analytics_service.py:685-726` against the real
> metric path). `AnalyticsService.get_low_stock` reads the DB FILE via the
> engine's read-only connection — do NOT re-point the ux_features test to it
> (would require the TestAnalyticsServiceRealDb temp-file pattern for no new
> coverage).

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/inventory_service.py tests/test_services/test_ux_features.py tests/test_services/test_analytics_service.py tests/test_services/test_inventory_service.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

`InventoryService` mixes inventory MUTATION (update/set/adjust) with READ-ONLY
reporting that belongs to the analytics domain (AGENTS.md: `services/analytics/`
owns read-only metrics). `get_low_stock_products` is a raw query duplicating
`LowStockMetric` — the dashboard already uses the metric via
`AnalyticsService.get_low_stock`, and the metric's threshold behavior is covered
by real tests (`test_analytics_service.py:685-726`). Removing it deletes the
duplicate rule source. `get_inventory_movements` (ledger view),
`get_inventory_value` (dashboard KPI) and `get_inventory_turnover` (tested;
pins cancelled-exclusion) stay.

## Current state

- `services/inventory_service.py:332-373` — `get_inventory_movements` — 3-arm
  UNION ledger view; called by `ui/inventory_view.py`. KEEP.
- `services/inventory_service.py:375-411` — `get_inventory_turnover` — KEEP
  (amendment: two real tests at `tests/test_services/test_inventory_service.py:286-305,329-348`
  pin its behavior incl. cancelled-sale exclusion; no production caller, but it
  is tested, working code — deleting it is deferred to a future decision).
- `services/inventory_service.py:413-426` — `get_low_stock_products(threshold=10)` —
  raw query duplicating `LowStockMetric` (`services/analytics/metrics.py:128-157`).
  Only caller: `test_low_stock_threshold` (`tests/test_services/test_ux_features.py:55-71`,
  using threshold=10/20/2 at :62,:67,:71). The dashboard uses
  `AnalyticsService.get_low_stock` (`ui/dashboard_view.py:346`).
- `services/inventory_service.py:257-280` — `get_inventory_value()` — dashboard
  KPI (`ui/dashboard_view.py:246`). KEEP.
- `AnalyticsService.get_low_stock(threshold)` — reads the DB FILE via the
  engine's read-only URI connection (`services/analytics/engine.py:26-41`); the
  `db_manager` fixture is in-memory, so re-pointing the ux_features test is NOT
  viable. Coverage of the metric's threshold behavior already exists in
  `tests/test_services/test_analytics_service.py:685-726`
  (`test_get_low_stock_wrapper` asserts thresholds 10 and 2;
  `test_manual_inventory_mutations_clear_analytics_low_stock_cache`).

**Repo conventions**:
- Reporting that is a metric belongs in `services/analytics/`; mutation +
  ledger belong in `InventoryService`.
- Dead-code deletions use the zero-reference guard (plan 011); deleting
  test-pinned working code requires the coverage to exist elsewhere.
- The dashboard's low-stock path is `AnalyticsService.get_low_stock` — the
  consolidated source.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| UX features tests | `.venv/bin/python -m pytest tests/test_services/test_ux_features.py` | all pass (after update) |
| Analytics tests | `.venv/bin/python -m pytest tests/test_services/test_analytics_service.py tests/analytics/` | all pass |
| Inventory tests | `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py tests/test_ui/test_inventory_view.py` | all pass (xvfb for UI) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `services/inventory_service.py`
- `tests/test_services/test_ux_features.py`

**Out of scope**:
- `get_inventory_movements`, `get_inventory_value`, `get_inventory_turnover` (KEEP — do not touch)
- `tests/test_services/test_inventory_service.py` (its turnover tests stay — do not touch)
- `tests/test_services/test_analytics_service.py` (its low-stock coverage stays — do not touch)
- `services/analytics/metrics.py` `LowStockMetric` (already the consolidated source)
- Any inventory mutation behavior

## Git workflow

- Branch: `advisor/050-inventory-reporting`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Delete get_low_stock_products

In `services/inventory_service.py`, delete `get_low_stock_products` (:413-426).

**Verify**: `grep -rn "get_low_stock_products" --include="*.py" services/ ui/ tests/` → no matches.

### Step 2: Delete the duplicated test

In `tests/test_services/test_ux_features.py`, delete `test_low_stock_threshold`
(:55-71 — the test that calls `get_low_stock_products` with thresholds 10/20/2).
Its coverage is duplicated by `test_get_low_stock_wrapper` and
`test_manual_inventory_mutations_clear_analytics_low_stock_cache` in
`tests/test_services/test_analytics_service.py:685-726` (real metric path).
Also remove any now-unused imports in that test file (run ruff to detect).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_ux_features.py` → all pass; `grep -rn "get_low_stock_products" --include="*.py" .` → no matches.

### Step 3: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- No new tests: the low-stock threshold coverage already lives in
  `tests/test_services/test_analytics_service.py:685-726` against the real
  metric path (dashboard path).
- `tests/test_services/test_inventory_service.py` turnover tests stay
  untouched (they pin `get_inventory_turnover`, which is kept).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "get_low_stock_products" --include="*.py" services/ ui/ tests/` returns no matches
- [ ] `get_inventory_turnover` still present in `services/inventory_service.py` AND its two tests still in `tests/test_services/test_inventory_service.py`
- [ ] `get_inventory_movements` and `get_inventory_value` still present in `services/inventory_service.py`
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A production caller of `get_low_stock_products` exists that grep missed.
- `test_ux_features.py` has OTHER tests that depend on `get_low_stock_products`
  beyond `test_low_stock_threshold`.
- Deleting `test_low_stock_threshold` leaves the file with unused fixture
  setup you cannot cleanly remove.

## Maintenance notes

- `InventoryService` now owns: mutations + the adjustment ledger
  (`get_inventory_movements`) + the dashboard value KPI + `get_inventory_turnover`
  (kept; tested). Any NEW inventory reporting metric belongs in
  `services/analytics/metrics.py`.
- The low-stock path is single-sourced: `LowStockMetric` →
  `AnalyticsService.get_low_stock` → dashboard/inventory views.
- `get_inventory_turnover` remains a candidate to become an analytics metric if
  a UI ever surfaces it — the tests pin its behavior for that migration.
- Reviewer should verify the inventory view's movements tab still shows
  adjustments/sales/purchases (unchanged).
