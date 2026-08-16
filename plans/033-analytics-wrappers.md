# Plan 033: Expose orphaned analytics metrics via AnalyticsService; consolidate dashboard low-stock

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> Touch only the files listed as in scope. If any STOP condition occurs, stop
> and report — do not improvise. When done, update the status row for this
> plan in `plans/README.md` — unless a reviewer dispatched you and told you
> they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 0b99aa5..HEAD -- services/analytics_service.py services/analytics/__init__.py ui/dashboard_view.py tests/test_services/test_analytics_service.py tests/analytics/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2 (backlog item — DIR-02 from the round-1 direction audit)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `0b99aa5`, 2026-08-16

## Why this matters

Two implemented, tested, documented analytics metrics are not exposed through
`AnalyticsService` (which wraps the other nine): `LowStockMetric` and
`InventoryAgingMetric` (`services/analytics/metrics.py:128,160`, exported in
`services/analytics/__init__.py`). Meanwhile the dashboard hand-rolls the
low-stock query via `inventory_service.get_low_stock_products`
(`ui/dashboard_view.py:328`-ish, `update_low_stock`) instead of the metric
engine — a parallel implementation that the audit (round 1, DIR-02) flagged.
This plan adds the two wrappers (following the existing 9-wrapper pattern)
and switches the dashboard's low-stock card to the wrapper, keeping the
read-only analytics contract as the single implementation.

## Current state

```python
# services/analytics_service.py — the existing wrapper pattern (e.g. :292-297)
@staticmethod
def get_sales_summary(start_date: str, end_date: str) -> dict[str, Any]:
    metric_result = AnalyticsEngine().execute_metric(
        SalesSummaryMetric(), start_date=start_date, end_date=end_date
    )
    return metric_result.data[0]  # (check the exact return shape used by siblings)
# ...and 8 more wrappers (get_sales_daily, get_top_selling_products, ...)
```

The two unwrapped metrics:
- `LowStockMetric` — params: `threshold` (default 10); output rows:
  `product_id, name, quantity` (metrics.py:128-157).
- `InventoryAgingMetric` — params: `days` (default 30); output rows:
  `product_id, name, stock_quantity, last_sold_date` (metrics.py:160-202).

Dashboard low-stock today (`ui/dashboard_view.py`, `update_low_stock`):
calls `self.inventory_service.get_low_stock_products(threshold)` and renders
a table — same data shape as the metric. `get_low_stock_products` lives in
`services/inventory_service.py:421-433`.

Existing tests that pin behavior:
- `tests/analytics/test_metrics.py` — `test_low_stock` (:156), `test_inventory_aging` (:169) — metric-level.
- `tests/test_services/test_analytics_service.py` — the real-DB wrapper tests
  (e.g. `get_sales_summary`) — the pattern for the new wrapper tests.
- `tests/test_ui/` — dashboard tests from plan 027
  (`tests/test_ui/test_dashboard_view.py`) render the dashboard; the
  low-stock table must keep rendering.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Analytics tests | `.venv/bin/python -m pytest tests/analytics tests/test_services/test_analytics_service.py` | all pass |
| UI tests | `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `services/analytics_service.py` — `get_low_stock(threshold=10)` and
  `get_inventory_aging(days=30)` wrappers (mirror the sibling wrappers'
  signature/return style exactly)
- `ui/dashboard_view.py` — `update_low_stock` switches from
  `inventory_service.get_low_stock_products` to the analytics wrapper
  (adjust imports accordingly)
- `tests/test_services/test_analytics_service.py` — real-DB wrapper tests
  for both new wrappers (seeded product/inventory, follow the existing
  real-DB class pattern)
- `SPECIFICATIONS.md` — if the analytics section lists available metrics,
  ensure the two are listed as service-exposed (check first)

**Out of scope** (do NOT touch):
- `services/inventory_service.py` — `get_low_stock_products` STAYS (it has a
  caller today; after this plan it becomes test-only or uncalled — per the
  zero-reference rule, if it ends up with zero callers, DELETE it in the same
  change and note it)
- The metrics themselves (`metrics.py`), the engine, cache semantics
- Any other dashboard behavior

## Git workflow

- Branch: `advisor/033-analytics-wrappers`
- Commit per step; message style follows the repo (`feat: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: The two wrappers

In `services/analytics_service.py`, add two static methods following the
exact pattern of the sibling wrappers (check `get_sales_summary` and one
parameterized sibling such as `get_top_selling_products` for the style):

```python
@staticmethod
def get_low_stock(threshold: int = 10) -> list[dict[str, Any]]:
    metric_result = AnalyticsEngine().execute_metric(
        LowStockMetric(), threshold=threshold
    )
    return metric_result.data  # mirror the sibling return shape

@staticmethod
def get_inventory_aging(days: int = 30) -> list[dict[str, Any]]:
    metric_result = AnalyticsEngine().execute_metric(
        InventoryAgingMetric(), days=days
    )
    return metric_result.data
```

(Add the imports for `LowStockMetric`/`InventoryAgingMetric` alongside the
existing metric imports. Verify `metric_result.data` is the shape the other
wrappers return — if they wrap in a dict, match that.)

**Verify**: `.venv/bin/python -m pytest tests/analytics` → all pass.

### Step 2: Dashboard uses the wrapper

In `ui/dashboard_view.py`, `update_low_stock`: replace the
`inventory_service.get_low_stock_products(threshold)` call with
`AnalyticsService.get_low_stock(threshold)` (the file already imports
`AnalyticsService`). Keep the rendering code (table rows) as-is — verify the
row keys match (`product_id, name, quantity` both sides).

Then apply the zero-reference rule to
`inventory_service.get_low_stock_products`: `rg -rn "get_low_stock_products"` —
if the only remaining hits are its definition (and tests), delete it and its
now-unused imports (F401 check).

**Verify**: `xvfb-run -a .venv/bin/python -m pytest tests/test_ui/test_dashboard_view.py tests/test_ui/test_inventory_view.py` → all pass.

### Step 3: Real-DB wrapper tests

In `tests/test_services/test_analytics_service.py` (the real-DB class,
following the existing seeded tests):

- `test_get_low_stock_wrapper` — seed a product with quantity < 10 (via the
  class's seeding helpers) → wrapper returns it with `quantity`; threshold
  param respected.
- `test_get_inventory_aging_wrapper` — seed a product with stock and no
  sales → wrapper returns it with `last_sold_date` None (or absent per the
  metric's output).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_analytics_service.py` → all pass.

### Step 4: Docs + full verification

1. Check `SPECIFICATIONS.md`/`docs/analytics.md` for the "Available Metrics"
   list; if `low_stock`/`inventory_aging` are listed as metrics but not as
   service methods, add a line noting they are exposed via
   `AnalyticsService.get_low_stock` / `get_inventory_aging`.
2. **Verify**:
   - `.venv/bin/python -m pytest` → all pass (modulo pre-existing worktree UI exceptions)
   - `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean

## Test plan

| Test | File | Case |
|------|------|------|
| get_low_stock wrapper | test_analytics_service.py | seeded low-stock product returned; threshold respected |
| get_inventory_aging wrapper | test_analytics_service.py | seeded aging product returned |
| (existing) dashboard render tests | test_dashboard_view.py | dashboard still renders with the wrapper |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `AnalyticsService.get_low_stock` and `get_inventory_aging` exist and call the respective metrics
- [ ] `rg -n "get_low_stock_products" ui/` exits 1 (dashboard switched); if `services/inventory_service.py` still defines it with zero callers, it was deleted
- [ ] `.venv/bin/python -m pytest tests/analytics tests/test_services/test_analytics_service.py tests/test_ui/test_dashboard_view.py` exits 0
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- The sibling wrappers' return shape differs from the plan's assumption
  (report the actual pattern).
- `get_low_stock_products` turns out to have OTHER callers beyond the
  dashboard (report them; don't delete).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- The analytics read-only contract is now the single implementation for
  operational alerts (low stock, aging); `inventory_service.get_low_stock_products`
  removal (if applicable) closes the parallel implementation.
- Reviewer scrutiny: cache behavior (AnalyticsService caches — the dashboard
  refresh path must still refresh after mutations; verify the existing
  `AnalyticsService.clear_cache` wiring covers the new wrapper usage), and
  that the dashboard table row keys didn't change.
