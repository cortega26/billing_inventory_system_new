# Plan 015: Exclude cancelled sales from every revenue/profit/statistics/turnover/movement report

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat b0dd06a..HEAD -- services/sale_service.py services/analytics/metrics.py services/inventory_service.py tests/test_services/test_sale_service.py tests/analytics/test_metrics.py tests/test_services/test_analytics_service.py tests/test_services/test_inventory_service.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `b0dd06a`, 2026-08-15

## Why this matters

`cancel_sale` restores stock and sets `status='cancelled'` but keeps
`total_amount`/`total_profit` on the row, and **no aggregate query filters on
status**. After the first voided sale, every headline number is permanently
wrong: "Ventas Totales", total profits, sale statistics, all nine analytics
date-range metrics, inventory turnover, and the movement ledger all count
cancelled sales as if they were real sales. There is no net-of-cancellations
number anywhere. This plan adds a single `status = 'confirmed'` filter to all
aggregate/report queries while leaving the sales list (audit view) untouched.

## Current state

Files in scope and their roles:

- `services/sale_service.py` — sale CRUD; contains the three revenue aggregates.
- `services/analytics/metrics.py` — the 9 date-range metric queries (analytics tab).
- `services/inventory_service.py` — movement ledger + turnover queries.
- `schema.sql` — defines the status column contract.
- `SPECIFICATIONS.md` — reporting semantics must be documented.

The status contract (already enforced by schema + model, both sides agree):

```
schema.sql:56:    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
```

`cancel_sale` only flips the status — totals stay on the row
(`services/sale_service.py:289-331`):

```python
DatabaseManager.execute_query(
    "UPDATE sales SET status = 'cancelled' WHERE id = ?", (sale_id,)
)
```

Aggregates today (no status filter anywhere):

```python
# services/sale_service.py:348-352 (get_total_sales)
query = """
    SELECT COALESCE(SUM(total_amount), 0) as total
    FROM sales
    WHERE date BETWEEN ? AND ?
"""
# services/sale_service.py:371-375 (get_total_profits) — same shape, SUM(total_profit)
# services/sale_service.py:618-624 (get_sale_statistics)
query = """
    SELECT
        COUNT(*) as total_sales,
        SUM(total_amount) as total_amount,
        SUM(total_profit) as total_profit
    FROM sales
    WHERE date BETWEEN ? AND ?
"""
```

Analytics metrics — all nine use `date(date) BETWEEN ? AND ?` (or
`date(s.date)`) with no status filter. Sites by line number in
`services/analytics/metrics.py`:

| Line | Metric class | Table alias | Predicate |
|------|--------------|-------------|-----------|
| 33 | SalesDailyMetric | — (`FROM sales`) | `WHERE date(date) BETWEEN ? AND ?` |
| 74 | WeekdaySalesMetric | — | same |
| 118 | TopProductsMetric | `s` | `WHERE date(s.date) BETWEEN ? AND ?` |
| 238 | DepartmentSalesMetric | `s` | same |
| 277 | ProfitTrendMetric | — | same |
| 310 | WeeklyProfitTrendMetric | — | same |
| 358 | ProductProfitMetric | `s` | same |
| 419 | ProfitMarginDistributionMetric | `s` (inner subquery) | same |
| 470 | SalesSummaryMetric | — | same |

Inventory ledger also counts cancelled sales as sold:

```python
# services/inventory_service.py:355-360 (get_inventory_movements, 'sale' union arm)
SELECT 'sale' as type, s.date, -si.quantity as quantity_change,
       'Sale' as reason
FROM sale_items si
JOIN sales s ON si.sale_id = s.id
WHERE si.product_id = ? AND s.date BETWEEN ? AND ?
# (no status filter — a cancelled sale appears as a stock deduction with no restore)

# services/inventory_service.py:391-396 (get_inventory_turnover)
WITH sales_data AS (
    SELECT si.product_id, SUM(si.quantity) as total_sold
    FROM sale_items si
    JOIN sales s ON si.sale_id = s.id
    WHERE s.date BETWEEN ? AND ?
    GROUP BY si.product_id
)
# (no status filter — cancelled quantities inflate the "sold" numerator)
```

Repo conventions that apply:

- Queries are parameterized; never interpolate values into SQL (use `?`).
- Money stays integer CLP; no decimal arithmetic in these changes.
- Tests use the real-DB `db_manager` fixture (`tests/conftest.py:22-49`) and
  module-level fixtures defined in `tests/test_services/test_sale_service.py:25-95`
  (`sale_service`, `sample_product`, `sample_customer`, `sample_sale_data`).
- User-facing strings are Spanish (no new user-facing strings needed here).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/analytics/test_metrics.py tests/test_services/test_analytics_service.py tests/test_services/test_inventory_service.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |
| Security | `.venv/bin/bandit -q -r database services utils --skip B101` | exit 0 |

## Scope

**In scope**:
- `services/sale_service.py` — the three aggregates only (lines 345-386, 612-634)
- `services/analytics/metrics.py` — the nine metric queries
- `services/inventory_service.py` — `get_inventory_movements` + `get_inventory_turnover`
- `tests/test_services/test_sale_service.py` — new exclusion tests
- `tests/analytics/test_metrics.py` — fixture status column + new test
- `tests/test_services/test_analytics_service.py` — new real-schema test
- `tests/test_services/test_inventory_service.py` — new exclusion tests
- `SPECIFICATIONS.md` — one line documenting that reports exclude cancelled sales

**Out of scope** (do NOT touch):
- `sale_service.get_all_sales`, `get_sale`, `get_sales_by_date_range` — the
  sales *list* intentionally shows cancelled sales for audit; only aggregates change.
- `cancel_sale` itself — do NOT zero `total_amount`/`total_profit` on cancel;
  the audit row keeps its history, reports exclude by status.
- Any other report/metric code not listed above.

## Git workflow

- Branch: `advisor/015-cancelled-sales-reports`
- Commit per step; message style follows the repo (`fix: ...`, `tests: ...` —
  see `git log --oneline -10`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the status filter to the three sale-service aggregates

In `services/sale_service.py`:

- `get_total_sales` (line ~348): change `WHERE date BETWEEN ? AND ?` to
  `WHERE date BETWEEN ? AND ? AND status = 'confirmed'`
- `get_total_profits` (line ~371): same change
- `get_sale_statistics` (line ~618): same change

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py -k "statistics or total"` → passes (existing tests use confirmed sales, so they must still pass; the new tests in Step 5 cover the cancelled case).

### Step 2: Add the status filter to the nine analytics metrics

In `services/analytics/metrics.py`, for each of the nine sites in the table
above, add the status predicate to the `WHERE` clause:

- For metrics with no table alias (`FROM sales`): add `AND status = 'confirmed'`
- For metrics joining `sales s` (alias `s`): add `AND s.status = 'confirmed'`
  - Careful with ProfitMarginDistributionMetric: the predicate is inside the
    inner subquery (`WHERE date(s.date) BETWEEN ? AND ?` at line 419) — add
    `AND s.status = 'confirmed'` there.
- Leave the `WHERE` clause ordering as-is except for appending the predicate;
  keep `get_parameters` unchanged.

**Verify**: `.venv/bin/python -m pytest tests/analytics/test_metrics.py` → passes (Step 3 updates the fixture so this remains true).

### Step 3: Add a `status` column to the analytics test fixture

`tests/analytics/test_metrics.py:45-51` builds a hand-rolled `sales` table
without `status`. Add the column to the fixture DDL:

```sql
CREATE TABLE sales (
    id INTEGER PRIMARY KEY,
    date TEXT,
    total_amount INTEGER,
    total_profit INTEGER,
    customer_id INTEGER,
    status TEXT NOT NULL DEFAULT 'confirmed'
);
```

Existing seeded rows get `'confirmed'` via the default, so all existing
assertions keep passing.

**Verify**: `.venv/bin/python -m pytest tests/analytics/test_metrics.py` → all pass.

### Step 4: Add the status filter to the inventory ledger queries

In `services/inventory_service.py`:

- `get_inventory_movements` — in the `'sale'` union arm (lines 355-360), add
  `AND s.status = 'confirmed'` to the `WHERE` clause.
- `get_inventory_turnover` — in the `sales_data` CTE (line 395), add
  `AND s.status = 'confirmed'`.

Rationale (document in the PR description): a cancelled sale restores stock
via `apply_batch_updates` with no ledger row, so showing its deduction without
a matching restore would make the movement ledger net-negative for a
zero-net event; turnover's "sold" numerator must count only real sales.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` → passes (existing movement/turnover tests use confirmed sales).

### Step 5: Add regression tests

In `tests/test_services/test_sale_service.py` (inside `TestSaleService`,
using the existing fixtures and the `test_cancel_sale_sets_status_cancelled`
test at line ~404 as the pattern for cancelling):

```python
def test_get_total_sales_excludes_cancelled_sales(
    self, sale_service, sample_sale_data, inventory_service, sample_product
):
    inventory_service.update_quantity(sample_product.id, 10.0)
    sale_id = sale_service.create_sale(**sample_sale_data)
    today = date.today().isoformat()
    assert sale_service.get_total_sales(today, today) > 0
    sale_service.cancel_sale(sale_id)
    assert sale_service.get_total_sales(today, today) == 0
```

- `test_get_total_profits_excludes_cancelled_sales` — same shape against `get_total_profits`.
- `test_get_sale_statistics_excludes_cancelled_sales` — create + cancel, then
  assert `stats["total_sales"] == 0`, `stats["total_amount"] == 0`,
  `stats["total_profit"] == 0`.

In `tests/analytics/test_metrics.py` (the `engine` fixture and
`metric = SalesDailyMetric(); result = engine.execute_metric(metric, ...)`
pattern from `test_sales_daily` at line 104; result rows live in
`result.data` as dicts):

```python
def test_cancelled_sale_excluded_from_sales_daily(engine, analytics_db_path):
    conn = sqlite3.connect(analytics_db_path)
    conn.execute(
        "INSERT INTO sales (id, date, total_amount, total_profit, customer_id, status)"
        " VALUES (3, ?, 500, 250, 1, 'cancelled')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
    )
    conn.commit()
    conn.close()
    start = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    result = engine.execute_metric(SalesDailyMetric(), start_date=start, end_date=end)
    assert sum(row["total_sales"] for row in result.data) == 3100
```

Use the existing `test_sales_daily` (line 104) for the exact date-range values
and result-row shape. Also add the same exclusion assertion to a
`test_cancelled_sale_excluded_from_sales_summary` variant (same seed, run
`SalesSummaryMetric`, assert `total_revenue == 3100` and `total_sales == 2`).

In `tests/test_services/test_analytics_service.py` (real schema — follow the
existing real-schema tests at lines ~658-683): seed a product + inventory,
create a sale via `SaleService`, `cancel_sale`, then assert
`AnalyticsService.get_sales_summary(start, end)` returns zeroed totals.

In `tests/test_services/test_inventory_service.py` (follow
`test_get_inventory_movements` at line ~215 and the module's setup fixtures):

- `test_movements_exclude_cancelled_sales` — set quantity, create a sale for
  `self.prod_id`, cancel it, assert `get_inventory_movements` contains no
  `'sale'`-type row for the product.
- `test_turnover_excludes_cancelled_sales` — same setup, assert
  `get_inventory_turnover` returns no entry for the product.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/analytics/test_metrics.py tests/test_services/test_analytics_service.py tests/test_services/test_inventory_service.py` → all pass, including the new tests.

### Step 6: Document the reporting semantics

In `SPECIFICATIONS.md`, in the reporting/metrics section, add one line stating
that all revenue, profit, statistics, turnover, and movement reports exclude
cancelled (`status = 'cancelled'`) sales, while the sales list retains them for
audit.

**Verify**: file contains the new line; no other spec section contradicts it
(grep `SPECIFICATIONS.md` for "cancel" to check existing wording).

### Step 7: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0
- `.venv/bin/bandit -q -r database services utils --skip B101` → exit 0

## Test plan

Covered in Step 5. Summary of the new tests:

| Test | File | Case |
|------|------|------|
| get_total_sales / profits / statistics exclusion | test_sale_service.py | cancelled sale excluded from all three aggregates |
| sales_daily + sales_summary exclusion | test_metrics.py | cancelled row not in metric output |
| get_sales_summary real-schema exclusion | test_analytics_service.py | service-level exclusion on the real schema |
| movements + turnover exclusion | test_inventory_service.py | cancelled sale leaves no ledger/turnover trace |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "status = 'confirmed'" services/sale_service.py services/analytics/metrics.py services/inventory_service.py` shows the filter in every aggregate (sale_service: 3 sites; metrics.py: 9 sites; inventory_service: 2 sites)
- [ ] `grep -n "date(date) BETWEEN" services/analytics/metrics.py` returns nothing
- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `.venv/bin/ruff check .` exits 0; `.venv/bin/black --check .` exits 0; `.venv/bin/pyright` exits 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts
  (the codebase has drifted since this plan was written).
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file.
- You discover that `status` values other than `confirmed`/`cancelled` can
  exist in the database (schema or data drift) — check with
  `.venv/bin/python -c "from database.database_manager import DatabaseManager; DatabaseManager.initialize(':memory:'); ..."` only if something in the suite suggests it.
- Existing tests fail because some *other* code path (not in scope) depends on
  aggregates including cancelled sales.

## Maintenance notes

- If a future feature adds new sale statuses (e.g. `refunded`), every
  aggregate must be revisited — this plan's filter is `= 'confirmed'`, so new
  statuses are excluded automatically, which is the intended default; document
  the choice then.
- `ui/sale_view.py` and `ui/dashboard_view.py` consume these aggregates; their
  displayed numbers will change (become correct) after this lands — no UI code
  change is needed.
- A reviewer should scrutinize: ProfitMarginDistributionMetric (subquery
  placement) and that the sales *list* queries were left untouched.
