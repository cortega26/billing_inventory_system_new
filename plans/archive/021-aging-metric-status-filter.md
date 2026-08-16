# Plan 021: InventoryAgingMetric must not count cancelled sales as "last sold"

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 9f606b4..HEAD -- services/analytics/metrics.py tests/analytics/test_metrics.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpt against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (found by the plan-015/019 midpoint gap review)
- **Category**: bug
- **Planned at**: commit `9f606b4`, 2026-08-15

## Why this matters

Plan 015 added `status = 'confirmed'` filters to the nine date-range metrics,
sale-service aggregates, and inventory movements/turnover — but the
midpoint gap review found a tenth site in the same family:
`InventoryAgingMetric` joins `sales` for `MAX(s.date)` with no status filter.
A product whose only sale was cancelled appears "recently sold" and drops out
of the aging report (dead-stock detection), even though the sale was voided.
One-line filter + one regression test.

## Current state

```python
# services/analytics/metrics.py:181-199 (InventoryAgingMetric.get_query)
return """
    SELECT
        p.id as product_id,
        p.name,
        i.quantity as stock_quantity,
        MAX(s.date) as last_sold_date
    FROM products p
    JOIN inventory i ON p.id = i.product_id
    LEFT JOIN sale_items si ON p.id = si.product_id
    LEFT JOIN sales s ON si.sale_id = s.id
    WHERE i.quantity > 0
    GROUP BY p.id
    HAVING last_sold_date IS NULL
       OR last_sold_date < date('now', '-' || ? || ' days')
    ORDER BY last_sold_date ASC
"""
```

All other metrics in this file now filter `s.status = 'confirmed'`; this one
does not. The status column contract: `schema.sql:56` —
`status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled'))`.

Test conventions: `tests/analytics/test_metrics.py` builds a hand-rolled
fixture (`analytics_db_path`) whose `sales` table now has a `status` column
with `DEFAULT 'confirmed'` (plan 015 added it). `engine.execute_metric(...)`
results expose rows as dicts via `.data`; `test_inventory_aging` at line ~169
is the existing pattern. The existing `test_inventory_aging` seeds a dead
stock product ("Old Phone", product 3) with no sales.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/analytics/test_metrics.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `services/analytics/metrics.py` — the `InventoryAgingMetric` query only
- `tests/analytics/test_metrics.py` — one regression test

**Out of scope** (do NOT touch):
- Any other metric, `engine.py`, `analytics_service.py`, indexes/migrations.

## Git workflow

- Branch: `advisor/021-aging-metric-status-filter`
- Commit per step; message style follows the repo (`fix: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the status filter

In `services/analytics/metrics.py`, `InventoryAgingMetric.get_query`, change
the `LEFT JOIN sales s ON si.sale_id = s.id` line so cancelled sales are
excluded. Correct shape (match the aliasing used by the other metrics):

```sql
LEFT JOIN sales s ON si.sale_id = s.id AND s.status = 'confirmed'
```

(Filtering on the join keeps the LEFT JOIN semantics — products with no
sales, or only cancelled sales, still appear with `last_sold_date IS NULL`,
which the HAVING clause already handles as "never sold".)

**Verify**: `.venv/bin/python -m pytest tests/analytics/test_metrics.py` → all pass.

### Step 2: Regression test

In `tests/analytics/test_metrics.py`, add a test following the
`test_inventory_aging` pattern (line ~169): seed a product with stock > 0
whose ONLY sale is cancelled, then assert it still appears in the
`inventory_aging` output (with `last_sold_date` None/absent) — i.e. the
cancelled sale must not make it look recently sold. A concrete shape:

```python
def test_inventory_aging_ignores_cancelled_sales(engine, analytics_db_path):
    # Product 3 (Old Phone, stock 50) has only a CANCELLED sale in the past:
    # it must still be reported as aging stock, not "recently sold".
    conn = sqlite3.connect(analytics_db_path)
    conn.execute(
        "INSERT INTO sales (id, date, total_amount, total_profit, customer_id, status)"
        " VALUES (3, ?, 100, 50, 1, 'cancelled')",
        ((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),),
    )
    conn.execute("INSERT INTO sale_items (id, sale_id, product_id, quantity, price)"
                 " VALUES (4, 3, 3, 1, 100)")
    conn.commit()
    conn.close()

    result = engine.execute_metric(InventoryAgingMetric(), days=30)
    aging = {row["product_id"]: row for row in result.data}
    assert 3 in aging  # still aging: the cancelled sale must not disqualify it
```

Check the exact field names against `test_inventory_aging` first and mirror
its assertions (e.g. whether `last_sold_date` is present as None or absent).

**Verify**: `.venv/bin/python -m pytest tests/analytics/test_metrics.py` → all pass, including the new test.

### Step 3: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass (modulo any pre-existing worktree UI-test exceptions — none in scope here)
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0

## Test plan

`test_inventory_aging_ignores_cancelled_sales` (tests/analytics/test_metrics.py):
cancelled-only-sales product still appears in aging output. Pattern:
`test_inventory_aging`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `rg -n "JOIN sales s ON si.sale_id = s.id" services/analytics/metrics.py` shows the `AND s.status = 'confirmed'` addition (one site)
- [ ] `rg -n "LEFT JOIN sales s" services/analytics/metrics.py` shows exactly one site, with the filter
- [ ] `.venv/bin/python -m pytest tests/analytics/test_metrics.py` exits 0 with the new test
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpt doesn't match the live code (the metric query moved or was rewritten).
- `test_inventory_aging`'s existing assertions break in a way that indicates the fixture's product-3 row now behaves differently (report; don't rewrite existing tests).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- This closes the last status-filter gap found by the plan-015/019 gap review.
  A future sweep should grep `services/analytics/metrics.py` for
  `JOIN sales` to verify every sales-joining query carries the filter.
- Reviewer scrutiny: the filter is on the JOIN (preserving LEFT JOIN
  semantics), not in the WHERE clause (which would silently drop
  never-sold products).
