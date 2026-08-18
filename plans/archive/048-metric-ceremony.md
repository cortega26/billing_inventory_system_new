# Plan 048: Slim the analytics Metric contract; kill metric boilerplate

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/analytics/contracts.py services/analytics/engine.py services/analytics/metrics.py services/analytics_service.py tests/analytics/ tests/test_services/test_analytics_service.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: 038 (SaleStatus enum — this plan builds on its bound-status predicates)
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The analytics layer carries ceremony: (1) every metric implements `description`
and `output_schema` — 22 property implementations that nothing ever reads
(`engine.py` consumes only `name`, `validate_params`, `get_query`,
`get_parameters`); (2) the 9 date-range metrics duplicate the same two-line
`validate_params` and the same `(start, end)` `get_parameters`; (3) the same
WHERE predicate (`date >= ? AND date < date(?, '+1 day') AND status = ?`)
appears verbatim 9 times; (4) `AnalyticsService` re-validates dates that the
metrics validate again (double validation per call) and repeats a ~20-line
fetch→remap→log skeleton 11 times; (5) `get_profit_and_volume_by_product` is a
test-only twin of `get_profit_by_product`. The real payload — the SQL per
metric — is valuable; the scaffolding around it is not.

## Current state

- `services/analytics/contracts.py:14-48` — `Metric` ABC with 5 abstract
  members: `name`, `description`, `output_schema`, `get_query`,
  `get_parameters`, `validate_params`. `engine.py:43-71` calls only
  `validate_params`/`get_query`/`get_parameters`; `description`/`output_schema`
  are never read (grep-verified).
- `services/analytics/metrics.py` — 11 metrics. Example (`SalesDailyMetric`,
  :9-39): 15 lines of scaffolding for 10 lines of SQL; `validate_params` =
  two `validate_date` calls (9 metrics identical); `get_parameters` =
  `(kwargs["start_date"], kwargs["end_date"])` (7 metrics identical).
  The predicate `date >= ? AND date < date(?, '+1 day') AND status = 'confirmed'`
  appears at :33, :74, :118, :238, :277, :310, :358, :419, :470 (9 sites).
- `services/analytics_service.py` — 11 date-range methods each do
  `validate_date(start); validate_date(end); _validate_date_range(...)` and
  then `AnalyticsEngine().execute_metric(MetricCls(), ...)` + dict-comprehension
  remap + logger + return (e.g. :34-55). `get_sales_summary` (:339) has NO
  `@lru_cache` (deliberate — see maintenance note; do NOT add one).
- `get_profit_and_volume_by_product` (:156-214) — wraps the same
  `ProductProfitMetric` as `get_profit_by_product` (:215) with a different
  projection; production callers: NONE (grep: tests only, e.g.
  `tests/test_services/test_analytics_service.py:309,331`).
- Tests: `tests/analytics/test_metrics.py` and
  `tests/test_services/test_analytics_service.py` pin every metric's output
  shape and the engine flow (mocking the engine where noted).

**Repo conventions**:
- `services/analytics/` is read-only by contract; the engine opens a separate
  read-only SQLite connection (documented exemption ARCH-08) — unchanged.
- Metrics are characterized by tests; behavior must be preserved exactly.
- `models/enums.py` constants are the single source for magic values.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Analytics tests | `.venv/bin/python -m pytest tests/analytics/ tests/test_services/test_analytics_service.py` | all pass |
| Business-switch tests | `.venv/bin/python -m pytest tests/test_services/test_business_switch.py` | all pass |
| UI analytics tests | `.venv/bin/python -m pytest tests/test_ui/test_analytics_view.py` | all pass (xvfb) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Security | `.venv/bin/bandit -q -r database services utils --skip B101` | exit 0 |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `services/analytics/contracts.py`
- `services/analytics/metrics.py`
- `services/analytics_service.py`
- `tests/analytics/`, `tests/test_services/test_analytics_service.py`

**Out of scope**:
- `services/analytics/engine.py` (execution flow stays; its call to
  `validate_params` stays valid because the base class provides it)
- Adding a cache to `get_sales_summary` (see maintenance note — it must stay uncached)
- Deleting `get_inventory_aging` or `get_sales_summary` (deliberate plan-033/022 surface; keep)

## Git workflow

- Branch: `advisor/048-metric-ceremony`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Slim the ABC

In `services/analytics/contracts.py`, remove the `description` and
`output_schema` abstract members from `Metric`. Keep `name`, `get_query`,
`get_parameters`, `validate_params`.

**Verify**: `grep -n "description\|output_schema" services/analytics/contracts.py` → no matches.

### Step 2: Add a DateRangeMetric base

In `contracts.py` (or `metrics.py` — choose contracts.py so engine stays
import-clean), add:

```python
class DateRangeMetric(Metric):
    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs["start_date"])
        validate_date(kwargs["end_date"])

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])
```

Import `validate_date` into contracts.py. Metrics that take `limit` (e.g.
`TopProductsMetric`) keep their own `get_parameters`/`validate_params`
(appending the limit) and call `super().validate_params(**kwargs)` first.

In `metrics.py`, convert the date-range metrics to subclass `DateRangeMetric`
and delete their now-inherited `validate_params`/`get_parameters` bodies.
Also delete `description`/`output_schema` from ALL 11 metrics.

**Verify**: `.venv/bin/python -m pytest tests/analytics/test_metrics.py` → pass.
`grep -c "def validate_params" services/analytics/metrics.py` → only the
limit-taking metrics remain (TopProductsMetric + any others with params).

### Step 3: Extract the shared WHERE predicate

In `metrics.py`, add a module constant:

```python
DATE_RANGE_STATUS_PREDICATE = (
    "date >= ? AND date < date(?, '+1 day') AND status = ?"
)
```

Replace the 9 inline predicates (`:33, :74, :118, :238, :277, :310, :358, :419, :470`)
with `{DATE_RANGE_STATUS_PREDICATE}` inside the f-string SQL, and change each
metric's `get_parameters`/base to append `SaleStatus.CONFIRMED.value` as the
third parameter (matching plan 038's bound-status change). For the two JOIN
forms (`s.date >= ? AND s.date < date(?, '+1 day') AND s.status = ?`), the
`date`/`status` column prefixes differ — define a second constant or interpolate
the prefix: `DATE_RANGE_STATUS_PREDICATE_ALIASED = "s.date >= ? AND s.date < date(?, '+1 day') AND s.status = ?"`.
Verify each metric's parameter tuple order matches the new placeholder count
(`(start, end, SaleStatus.CONFIRMED.value)` or `(start, end, limit, status)`).

**Verify**: `.venv/bin/python -m pytest tests/analytics/ tests/test_services/test_analytics_service.py` → pass.
`grep -c "date >= ? AND date < date(?, '+1 day')" services/analytics/metrics.py` → only the constant definitions remain (2).

### Step 4: AnalyticsService — drop double validation + add a helper

In `services/analytics_service.py`:
- Remove the duplicated `validate_date(start_date)` / `validate_date(end_date)`
  / `_validate_date_range(...)` calls from the date-range methods (the
  metric's `validate_params` now validates in the engine; cache-hit paths skip
  validation today anyway because `lru_cache` returns before the body runs).
- Add a private helper:
  ```python
  @staticmethod
  def _execute_metric(metric: Metric, row_mapper, **kwargs) -> list:
      result = AnalyticsEngine().execute_metric(metric, **kwargs)
      return [row_mapper(row) for row in result.data]
  ```
  and refactor the 11 methods to use it (each method keeps its own
  `row_mapper` lambda + logger.info line + return). The methods KEEP their
  `@lru_cache` + `@db_operation` + `@handle_exceptions` decorators unchanged.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_analytics_service.py` → pass.

### Step 5: Delete the twin profit wrapper

In `services/analytics_service.py`, delete `get_profit_and_volume_by_product`
(:156-214) and its entry in `clear_cache` (:373). In
`tests/test_services/test_analytics_service.py`, delete
`test_get_profit_and_volume_by_product_uses_metric_engine_and_preserves_output_shape`
(:309) and any other test calling the method.

**Verify**: `grep -rn "get_profit_and_volume_by_product" --include="*.py" .` → no matches.

### Step 6: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/bandit -q -r database services utils --skip B101`
→ exit 0; `.venv/bin/ruff check .` → exit 0; `.venv/bin/black --check .` → exit 0;
`.venv/bin/pyright` → exit 0.

## Test plan

- The existing analytics suites pin every metric's output shape — they are the
  regression net; run them after each step.
- Add one test in `tests/analytics/test_metrics.py` asserting
  `DATE_RANGE_STATUS_PREDICATE` contains the three placeholders and that
  `SalesDailyMetric().get_parameters(...)` returns 3 items after plan 038.
- The deleted twin's coverage: `get_profit_by_product` already has tests
  (`test_get_profit_by_product...`) — no coverage gap.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "get_profit_and_volume_by_product" --include="*.py" .` returns no matches
- [ ] `grep -n "def description\|def output_schema" services/analytics/` returns no matches
- [ ] `grep -c "date >= ? AND date < date(?, '+1 day')" services/analytics/metrics.py` ≤ 2 (constants only)
- [ ] `grep -c "def validate_params" services/analytics/metrics.py` ≤ 3 (only limit-taking metrics)
- [ ] New predicate test exists and passes
- [ ] `.venv/bin/bandit -q -r database services utils --skip B101` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A metric test fails on output shape after the refactor (the SQL must be
  byte-equivalent apart from the extracted predicate — if a result changes,
  report, do not adjust the test).
- Removing service-side date validation lets an invalid date reach a CACHE-MISS
  path with a different exception type than before (verify the engine's
  `validate_params` raises `ValidationException` like the service did).
- The `get_profit_and_volume_by_product` clear_cache entry is needed by
  another clear path.

## Maintenance notes

- **DO NOT add `@lru_cache` to `get_sales_summary`**: the analytics engine
  follows the active business (plan 022 Phase E), and a cache keyed only by
  date args would serve stale cross-business results — `test_business_switch.py`
  pins the uncached behavior. Its missing cache is correct by design.
- Adding a metric is now: subclass `DateRangeMetric` (or `Metric`), implement
  only `get_query`. No contract member beyond `name` + query is needed.
- Plan 038's bound-status predicates are the reason the shared predicate takes
  a status parameter — if 038 hasn't landed yet, run it first (this plan's
  predicate constant assumes it).