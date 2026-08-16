# Plan 005: Sales-table batching and refresh-wave coalescing

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
- **Risk**: MED
- **Depends on**: none
- **Category**: perf
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

Two performance defects compound on the UI thread:

1. **N+1 customer lookups per sales-table render.** `update_sale_table`
   (`ui/sale_view.py:1035-1043`) calls `self.customer_service.get_customer(sale.customer_id)`
   once per row (up to 100 rows per page). `get_customer`
   (`services/customer_service.py:170-196`) is uncached and runs a real query —
   101 queries per render, synchronously on the UI thread, re-executed on every
   refresh (F5, every sale event).
2. **Refresh storm on every mutation.** `MutationCoordinator.finalize_mutation`
   (`services/mutation_coordinator.py:33-41`) emits `inventory_changed` once PER
   PRODUCT, then `sale_added`. `MainWindow.on_inventory_changed`
   (`ui/main_window.py:346-347`) refreshes FIVE tabs per signal
   (`INVENTORY_REFRESH_TARGETS`), and `sale_added` fires another five-tab wave
   (`main_window.py:69-74,321-323`). A 20-item sale = 21 waves x 5 tabs of
   synchronous UI-thread work — checkout freezes at scale.

## Current state

- `ui/sale_view.py:1035-1043`:
  ```python
  def update_sale_table(self, sales: list[Sale]):
      self.sale_table.setRowCount(len(sales))
      for row, sale in enumerate(sales):
          customer = (
              self.customer_service.get_customer(sale.customer_id)
              if sale.customer_id is not None
              else None
          )
  ```
- `ui/sale_view.py:1022-1027` — the refresh is scheduled via
  `QTimer.singleShot(0, ...)` (UI thread).
- `services/customer_service.py:170-196` — `get_customer` (no cache).
- `services/mutation_coordinator.py:33-41` — per-product `inventory_changed`
  emission loop.
- `ui/main_window.py:69-89` — the five refresh-target tuples; `:346-347`
  `on_inventory_changed` → `refresh_relevant_views(INVENTORY_REFRESH_TARGETS)`;
  `:356-360` — `refreshed_tabs` set already dedupes within ONE call (the intent
  exists; cross-signal dedup does not).
- `ui/dashboard_view.py:66-74` — 5 `MetricWidget`s also run their value functions
  directly on `sale_added`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Sale-view tests | `.venv/bin/python -m pytest tests/test_ui/test_sale_view_helpers.py tests/test_ui/test_sale_view_tables.py -q` | all pass (needs display/xvfb) |
| Service tests | `.venv/bin/python -m pytest tests/test_services -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `ui/sale_view.py` — `update_sale_table` customer batching
- `services/customer_service.py` — a batched `get_customers_by_ids` method (or
  equivalent), OR reuse an existing loader if one exists (check first)
- `ui/main_window.py` — refresh coalescing (debounce) only; no signal signature changes
- `tests/test_ui/`, `tests/test_services/test_customer_service.py`

**Out of scope**:
- `services/mutation_coordinator.py` signal semantics (still one event per product — coalescing happens at the refresh boundary)
- `ui/dashboard_view.py` metric logic
- Worker threads / full offload — out of scope
- `services/sale_service.py::get_customer_sales` N+1 (`:160-174`) — has no production caller today; leave it (noted in plan 011)

## Git workflow

- Branch: `advisor/005-perf-batching`
- Commit messages: `perf: batch customer lookups in sales table`, `perf: coalesce view refreshes within one event-loop pass`
- Do NOT push unless instructed.

## Steps

### Step 1: Batched customer lookup

- In `services/customer_service.py`, add a method that fetches customers by a
  list of IDs with ONE query: `get_customers_by_ids(customer_ids: list[int]) -> dict[int, Customer]`
  (or `list[Customer]` if a dict is awkward — pick the shape that fits
  `update_sale_table`'s use). Reuse the same SELECT shape as `get_customer`
  (`services/customer_service.py:170-196`) with `WHERE c.id IN (...placeholders)`
  — mirror the placeholder pattern in `services/sale_service.py:208-217`.
  Handle the empty-list case (return `{}` without issuing `IN ()`).
- In `ui/sale_view.py::update_sale_table`, fetch the page's customer map ONCE
  before the row loop:
  ```python
  customer_ids = [sale.customer_id for sale in sales if sale.customer_id is not None]
  customers = self.customer_service.get_customers_by_ids(customer_ids) if customer_ids else {}
  ```
  and replace the per-row call with `customers.get(sale.customer_id)` (keep the
  `None` branch for deleted customers — `ui/sale_view.py:1049-1059`).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_customer_service.py -q` → all pass; add a test asserting `get_customers_by_ids` issues ONE query (count `DatabaseManager.fetch_all` calls via the `mocker` pattern used elsewhere in that file) and returns the map.

### Step 2: Coalesce refresh waves

In `ui/main_window.py::refresh_relevant_views`, add per-tab coalescing so that
multiple signals in the same Qt event-loop pass trigger at most one refresh per
tab:

- Keep a `set[str]` of pending tab names on the window (e.g. `self._pending_refresh_tabs`).
- `refresh_relevant_views` becomes: add targets to the pending set; if a
  `QTimer.singleShot(0, ...)` flush is not already scheduled, schedule it; the
  flush drains the set and refreshes each tab once (reusing the existing
  per-tab refresh call and the `refreshed_tabs` dedup).
- Preserve the existing public behavior: a direct call with `target_tab_names`
  still refreshes promptly (the flush is deferred by one event-loop pass —
  visually identical for the user).
- Do NOT change any signal signature or `MutationCoordinator` emissions.

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_main_window_helpers.py -q` (needs display) → all pass; add one test: emit `inventory_changed` twice + `sale_added` in one pass (via `event_system`), then `QTest.qWait` for the flush, and assert each view's refresh method was invoked ONCE (mock the per-view refresh methods; the existing refresh-once tests in `test_main_window_helpers.py:178-207` are the pattern to extend).

### Step 3: Regression guard

Add a comment-free assertion test in `tests/test_services/` (or extend the
existing coordinator tests in `tests/test_services/test_ux_features.py` if
present) that `MutationCoordinator.finalize_mutation` still emits one
`inventory_changed` per distinct product and one final signal — pinning the
contract the coalescing depends on.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_ux_features.py -q` → all pass.

## Test plan

- `get_customers_by_ids`: empty list → `{}`, no query; N ids → 1 query; deleted
  customer ids simply absent from the map (no crash).
- Refresh coalescing: N signals in one pass → 1 refresh per affected tab;
  signals in separate passes → separate refreshes.
- Coordinator contract: 1 signal per distinct product + 1 final signal (already
  partially covered; extend if needed).

## Done criteria

- [ ] `.venv/bin/python -m pytest tests/test_ui tests/test_services/test_customer_service.py tests/test_services/test_ux_features.py -q` exits 0
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] `grep -n "get_customer(sale.customer_id)" ui/sale_view.py` → no matches (the N+1 is gone)
- [ ] New tests exist for batched lookup (1 query) and coalesced refresh (1 per tab per pass)
- [ ] No files outside the in-scope list are modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- The existing refresh-once tests in `test_main_window_helpers.py` conflict with
  the coalescing change (e.g., they assert synchronous refresh) — STOP and
  report; the coalescing design may need a synchronous-first flush.
- `get_customer` turns out to be cached or trivial after all (the excerpt
  doesn't match) — STOP and report.
- A deleted-customer test path breaks (the `None` branch) — the map must absorb
  missing ids; if it crashes, STOP and report.

## Maintenance notes

- If a future refund/returns flow emits new signals, the coalescer absorbs them
  automatically (that is the point).
- The 1-per-pass coalescing bounds staleness to one event-loop tick (~16ms);
  if analytics-heavy waves still stall the UI, the next step is worker-thread
  offload (deliberately out of scope).
- Reviewer: confirm no signal was dropped — only deferred within one pass.
