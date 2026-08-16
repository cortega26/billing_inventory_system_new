# Plan 009: Inventory + analytics real-DB guard tests

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

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

Two service layers are tested only against mocks or hand-seeded schemas, so
their core guards run unprotected:

1. **Inventory service tests are 100% mock-based.**
   `tests/test_services/test_inventory_service.py` patches
   `InventoryService.update_quantity` in every test and asserts call arguments —
   it tests dispatch, not the guards. The real logic — negative-stock rejection
   (`services/inventory_service.py:104-123`), the CREATE branch for missing
   inventory, `set_quantity`'s transaction + `inventory_adjustments` row
   (`:218-253`), `adjust_inventory` (`:294-332`), `get_inventory_value`,
   `get_inventory_movements`, `get_inventory_turnover` (`:343-418`) — has no
   direct real-DB coverage. AGENTS.md's "Inventory must never become negative"
   invariant is protected only transitively.
2. **Analytics service tests use a mock DatabaseManager.**
   `tests/test_services/test_analytics_service.py:27-30` overrides the
   `db_manager` fixture with `mock_database`; the real SQL in
   `services/analytics/metrics.py` is only tested against a hand-rolled minimal
   schema (`tests/analytics/test_metrics.py:32-59`), not the app schema — real
   schema drift passes silently. The read-only contract ("must never mutate
   business tables" per AGENTS.md) has no regression guard.

## Current state

- `tests/test_services/test_inventory_service.py:10,22,35,50` — every test
  `@patch`es `update_quantity` (or similar) and asserts arguments.
- `tests/test_services/test_ux_features.py` (`TestUXFeatures:130-198`) — DOES
  test `set_quantity`/`get_low_stock_products` against the real `db_manager`
  fixture — the pattern to follow.
- `services/inventory_service.py:218-253` — `set_quantity` transaction:
  `_modify_inventory(...UPDATE)` + `INSERT INTO inventory_adjustments` +
  `AuditService.log_operation`.
- `services/inventory_service.py:343-418`-ish — `get_inventory_value`,
  `get_inventory_movements`, `get_inventory_turnover` (verify line ranges when
  editing; they run SQL over `inventory_adjustments`/`sales`).
- `tests/test_services/test_analytics_service.py:27-30` — overrides
  `db_manager` with `mock_database`; `services/analytics/metrics.py` —
  SELECT-only SQL for 9+ metrics.
- `tests/analytics/test_metrics.py:32-59` — hand-seeded minimal schema.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Inventory tests | `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py tests/test_services/test_ux_features.py -q` | all pass |
| Analytics tests | `.venv/bin/python -m pytest tests/analytics tests/test_services/test_analytics_service.py -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `tests/test_services/test_inventory_service.py` — real-DB tests (rewrite or add; keep the dispatch tests only if they add value beyond the real-DB ones)
- `tests/test_services/test_analytics_service.py` — ONE real-DB integration test class (do not convert the whole file)
- `tests/analytics/test_metrics.py` — only if the real-schema test needs a shared seeding helper (prefer new test, keep existing tests)

**Out of scope**:
- `services/inventory_service.py`, `services/analytics_service.py`, `services/analytics/*` — NO production changes (if a test exposes a bug, write the failing test and STOP/report)
- Performance of metrics — this is correctness coverage
- `tests/test_critical_backend_flows.py` — leave untouched

## Git workflow

- Branch: `advisor/009-real-db-guard-tests`
- Commit messages: `test: cover inventory guards against real database`, `test: run analytics metrics against real schema and assert read-only`
- Do NOT push unless instructed.

## Steps

### Step 1: Inventory real-DB guard tests

Add a new test class in `tests/test_services/test_inventory_service.py` using
the `db_manager` fixture and the `sample_product` pattern from
`tests/test_services/test_product_service.py` (create a product, which creates
an inventory row). Cover:

1. `update_quantity` negative rejection: quantity 0 → `update_quantity(id, -1.0)`
   raises `ValidationException`, quantity stays 0.
2. `update_quantity` CREATE branch: delete the inventory row (or create a
   product whose inventory row is removed directly via
   `DatabaseManager.execute_query("DELETE FROM inventory WHERE product_id=?")`),
   then `update_quantity(id, 5.0)` creates the row with 5.0.
3. `update_quantity` rounding: `update_quantity(id, 0.123456)` → stored
   quantity rounds to 3 decimals.
4. `set_quantity`: sets value, writes ONE `inventory_adjustments` row with
   correct `quantity_change`, and one audit row; `set_quantity(id, same_value)`
   writes a 0-change adjustment row (pin current behavior).
5. `adjust_inventory` happy + sad path: positive adjust adds a row and quantity;
   a negative adjust that would go below zero raises `ValidationException` and
   leaves quantity + no adjustment row.
6. `get_inventory_value` / `get_inventory_movements` / `get_inventory_turnover`
   — one happy-path smoke each (call with a seeded product, assert shape/values;
   follow how `tests/test_services/test_ux_features.py` calls them if it does,
   else assert basic non-empty output for the seeded data).

Keep the existing dispatch tests ONLY if they assert something the real-DB
tests don't (e.g., `emit_events=False` propagation); otherwise delete them.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py -q` → all pass. `grep -n "@patch" tests/test_services/test_inventory_service.py | wc -l` → 0 if you removed all mocks (record the count either way).

### Step 2: Analytics real-schema integration test

In `tests/test_services/test_analytics_service.py`, add ONE test class that
uses the real `db_manager` fixture (do NOT use `mock_database`):

1. Seed via the fixture + services (create product with price, create one sale
   via `SaleService.create_sale` — mirror the seeding in
   `tests/test_critical_backend_flows.py`).
2. Run 2-3 metrics through `AnalyticsService` (e.g., `get_total_sales(range)`,
   `get_top_selling_products(range)`, `get_sales_by_weekday(range)`) and assert
   output shape + expected values for the seeded data.
3. **Read-only assertion**: capture `SELECT COUNT(*)` for `sales`,
   `sale_items`, `inventory`, `inventory_adjustments`, `products` before and
   after the metric calls — assert unchanged.
4. Assert `AnalyticsService.clear_cache()` runs without error after the calls.

**Verify**: `.venv/bin/python -m pytest tests/analytics tests/test_services/test_analytics_service.py -q` → all pass.

## Test plan

- Inventory: the 6 named cases (negative rejection, CREATE branch, rounding,
  set_quantity trail, adjust happy/sad, read-only-metrics smoke).
- Analytics: real-schema metric output + read-only row-count assertion +
  cache-clear smoke.
- Patterns: `tests/test_services/test_ux_features.py` (real-DB service tests),
  `tests/test_critical_backend_flows.py` (seeding).

## Done criteria

- [ ] `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py tests/test_services/test_ux_features.py tests/analytics tests/test_services/test_analytics_service.py -q` exits 0
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] Inventory negative-rejection and CREATE-branch tests exist (grep in the file)
- [ ] Analytics read-only row-count assertion exists
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] No production files modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any new test exposes a production bug (e.g., `set_quantity` writes a phantom
  adjustment, or a metric mutates) — write the failing test, then STOP and
  report. Do NOT fix production code inside this plan.
- `get_inventory_turnover`/`get_inventory_movements` have signatures that don't
  match the excerpts — locate the real signatures from the code and adapt the
  test; only STOP if the behavior contradicts the excerpts.
- The analytics engine's read-only connection cannot open the in-memory
  `db_manager` DB (it opens its own `mode=ro` file connection —
  `services/analytics/engine.py:19-34`) — if the real-`db_manager` test cannot
  reach the seeded data, use a temp-file DB for this test class (see
  `database/__init__.py::init_db(db_path=...)` for how tests elsewhere create
  file DBs) and say so in the report.

## Maintenance notes

- The read-only assertion is the contract guard for `services/analytics/`
  per AGENTS.md.
- If plan 004 changes quantity storage types, the inventory assertions here
  (3-decimal rounding) are the pin that catches regressions.
- Reviewer: confirm the analytics test class uses the real fixture, not the
  mock override.
