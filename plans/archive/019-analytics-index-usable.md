# Plan 019: Make analytics date-range queries index-usable

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat b0dd06a..HEAD -- services/analytics/metrics.py tests/analytics/test_metrics.py tests/test_services/test_analytics_service.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plan 015 (both edit `metrics.py`; run 015 first, then this plan)
- **Category**: perf
- **Planned at**: commit `b0dd06a`, 2026-08-15

## Why this matters

Every analytics date-range metric filters with `date(date) BETWEEN ? AND ?`
(or `date(s.date)`). SQLite cannot use the existing `idx_sales_date` /
covering indexes for that predicate — verified with `EXPLAIN QUERY PLAN`
(5k-row in-memory DB): `date(date) BETWEEN` yields a full table SCAN, while a
direct column comparison uses the index. Every open of the analytics tab runs
~7 of these metrics, so each open scans the whole sales ledger, growing
linearly with history. The index migrations were deliberately built for these
queries (`idx_sales_date`, `idx_sales_covering`); the fix makes them usable.

## Current state

All nine date-range metrics in `services/analytics/metrics.py` use the
function-wrapped predicate (line numbers verified):

| Line | Metric | Predicate |
|------|--------|-----------|
| 33 | SalesDailyMetric | `WHERE date(date) BETWEEN ? AND ?` |
| 74 | WeekdaySalesMetric | same |
| 118 | TopProductsMetric | `WHERE date(s.date) BETWEEN ? AND ?` |
| 238 | DepartmentSalesMetric | same |
| 277 | ProfitTrendMetric | `WHERE date(date) BETWEEN ? AND ?` |
| 310 | WeeklyProfitTrendMetric | same |
| 358 | ProductProfitMetric | `WHERE date(s.date) BETWEEN ? AND ?` |
| 419 | ProfitMarginDistributionMetric | same (inner subquery) |
| 470 | SalesSummaryMetric | `WHERE date(date) BETWEEN ? AND ?` |

Representative current query (`metrics.py:26-36`):

```python
def get_query(self, **kwargs) -> str:
    return """
        SELECT
            strftime('%Y-%m-%d', date) as date,
            SUM(total_amount) as total_sales,
            COUNT(*) as sale_count
        FROM sales
        WHERE date(date) BETWEEN ? AND ?
        GROUP BY strftime('%Y-%m-%d', date)
        ORDER BY date ASC
    """
```

Data shape: the app stores sale dates as `YYYY-MM-DD` strings
(`validate_date` in `sale_service.py:48-49`; the SQLite default datetime
strftime is not used on writes). The date column is indexed
(`idx_sales_date` — see `scripts/check_schema_drift.py:64-70` canonical set).

Semantics to preserve: the end date is **inclusive** — a sale with
`date = '2026-08-15'` must be included when `end_date = '2026-08-15'`. The
range-shift form below keeps this for both date-only and timestamp values.

Test fixtures that matter:

- `tests/analytics/test_metrics.py:45-51` — hand-built `sales` table; rows
  seeded with `%Y-%m-%d %H:%M:%S` timestamps (`:81-89`). Assertions on
  daily/weekly groupings must keep passing.
- `tests/test_services/test_analytics_service.py:658-683` — real-schema tests
  for `get_sales_summary`, `get_top_selling_products`, `get_sales_by_weekday`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/analytics/test_metrics.py tests/test_services/test_analytics_service.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `services/analytics/metrics.py` — the nine predicates only
- `tests/analytics/test_metrics.py` — boundary regression test
- `tests/test_services/test_analytics_service.py` — multi-day real-schema assertion (optional but preferred)

**Out of scope** (do NOT touch):
- `services/analytics/engine.py`, `analytics_service.py` — query execution and
  service wrappers are unchanged; `get_parameters` is unchanged.
- `services/sale_service.py:562-567` (`get_sales_by_date_range`) — already uses
  a direct `date BETWEEN ? AND ?` on the column; leave it.
- Any index/migration work (plan 004 already owns the canonical index set).
- The `status` filtering from plan 015 — if plan 015 has landed, its added
  predicates must be preserved in the rewritten queries; if plan 015 has NOT
  landed yet, do not add status filters here (that's plan 015's job).

## Git workflow

- Branch: `advisor/019-analytics-index-usable`
- Commit per step; message style follows the repo (`perf: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Rewrite the nine predicates as direct-column range comparisons

In `services/analytics/metrics.py`, replace every `date(col) BETWEEN ? AND ?`
with the range-shift form:

- `FROM sales` queries (no alias): `WHERE date >= ? AND date < date(?, '+1 day')`
- `sales s` queries: `WHERE s.date >= ? AND s.date < date(?, '+1 day')`
  (in ProfitMarginDistributionMetric the predicate lives in the inner
  subquery's `WHERE` — same replacement there)

`get_parameters` stays exactly as-is (returns `(start_date, end_date)`).

Why this form: `col >= start` + `col < date(end, '+1 day')` keeps the end date
inclusive and is a pure column comparison, letting SQLite use
`idx_sales_date`. Do NOT use `date(col) BETWEEN ... AND date(...)` — that
still wraps the column in a function.

**Verify**: `.venv/bin/python -m pytest tests/analytics/test_metrics.py` → all pass.

### Step 2: Prove the index is now used

With the project venv, run an in-memory probe that mirrors the production
query shape:

```bash
.venv/bin/python - <<'EOF'
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, date TEXT, total_amount INTEGER, total_profit INTEGER, customer_id INTEGER)")
conn.execute("CREATE INDEX idx_sales_date ON sales (date)")
# old shape
plan1 = conn.execute("EXPLAIN QUERY PLAN SELECT SUM(total_amount) FROM sales WHERE date(date) BETWEEN '2026-01-01' AND '2026-01-31'").fetchall()
# new shape
plan2 = conn.execute("EXPLAIN QUERY PLAN SELECT SUM(total_amount) FROM sales WHERE date >= '2026-01-01' AND date < date('2026-01-31', '+1 day')").fetchall()
print("old:", plan1[0][3])
print("new:", plan2[0][3])
EOF
```

Expected: `old: SCAN sales`, `new: SEARCH sales USING INDEX idx_sales_date`.

**Verify**: output matches the expected lines above.

### Step 3: Add boundary regression tests

In `tests/analytics/test_metrics.py`, add a test that pins the inclusive-end
semantics (use the `analytics_db_path` fixture pattern from lines 25-93; it's
a plain `sqlite3` file you can reopen, and `engine.execute_metric(...)`
results expose rows as dicts via `.data` — see `test_sales_daily` at line 104):

```python
def test_sales_daily_range_includes_end_date_exactly_once(engine, analytics_db_path):
    # Insert: one sale ON the end date (included), one sale at midnight the
    # next day (excluded). Use far-past dates so the fixture's now-relative
    # seed rows (ids 1-2) can never fall inside the queried range.
    conn = sqlite3.connect(analytics_db_path)
    end = "2020-01-15"
    conn.execute(
        "INSERT INTO sales (id, date, total_amount, total_profit, customer_id)"
        " VALUES (3, ?, 111, 11, 1)",
        (end,),
    )
    conn.execute(
        "INSERT INTO sales (id, date, total_amount, total_profit, customer_id)"
        " VALUES (4, ?, 222, 22, 1)",
        (end + " 00:00:00",),
    )
    conn.commit()
    conn.close()

    result = engine.execute_metric(
        SalesDailyMetric(), start_date="2020-01-14", end_date=end
    )
    # Sum of total_sales across returned days == 111 only (222 must be excluded)
    assert sum(row["total_sales"] for row in result.data) == 111
```

Boundary reasoning: `date('2020-01-15', '+1 day')` is `2020-01-16`, so the
midnight value `'2020-01-16 00:00:00'` is excluded, and the end-date sale
`'2020-01-15'` is included — exactly the semantics the old
`date(date) BETWEEN` form had.

In `tests/test_services/test_analytics_service.py`, extend the existing
real-schema coverage with a multi-day range assertion for
`get_sales_summary` (seed two sales on different days via `SaleService`,
query the full range, assert both amounts are summed) — follow the seeding
pattern at lines 658-683.

**Verify**: `.venv/bin/python -m pytest tests/analytics/test_metrics.py tests/test_services/test_analytics_service.py` → all pass, including the new tests.

### Step 4: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0

## Test plan

| Test | File | Case |
|------|------|------|
| test_sales_daily_range_includes_end_date_exactly_once | test_metrics.py | end-date sale included; next-day midnight excluded (pins the shift semantics) |
| multi-day get_sales_summary | test_analytics_service.py | two-day range sums both days on the real schema |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "date(date) BETWEEN\|date(s.date) BETWEEN" services/analytics/metrics.py` returns nothing
- [ ] `grep -c "+1 day" services/analytics/metrics.py` shows 9 (one per metric)
- [ ] Step 2's probe prints `new: SEARCH sales USING INDEX idx_sales_date`
- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts.
- A test fails because a metric's grouping output changed (e.g. a
  `GROUP BY strftime('%Y-%m-%d', date)` row moved) — that signals a semantic
  difference the plan didn't anticipate; report with the failing assertion.
- Plan 015's status filter is missing from `metrics.py` even though plan 015
  is marked DONE (don't silently re-add it — report the drift).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- The range-shift form is the house pattern for date filters on indexed
  columns; new metrics must not reintroduce `date(col) BETWEEN`.
- The `tests/analytics/test_metrics.py` fixture uses timestamp strings; real
  data is date-only. The boundary test covers both at the exact midnight edge
  — if the app ever starts storing timestamps, revisit the boundary test.
- A reviewer should scrutinize: ProfitMarginDistributionMetric's subquery
  placement, and that `get_parameters` was not touched.
