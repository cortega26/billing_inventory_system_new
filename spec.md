# Execution Spec — Plans 015–020 (second audit round)

Planned at commit `b0dd06a`. Status ledger: `todo.md`. This file is the spec for
the *execution program*: implement → verify → review → merge → push → archive,
one plan at a time, in dependency order.

## Goals

1. Land all six vetted findings from the 2026-08-15 adversarial audit as
   reviewed, merged, pushed commits on `main`.
2. Every plan must satisfy its own machine-checkable done criteria before merge.
3. No production behavior change outside each plan's declared scope.
4. `plans/README.md` stays in sync (status → DONE, files archived) as plans land.

## Program order and dependencies

| # | Plan | Depends on | Merge branch |
|---|------|-----------|--------------|
| 1 | 015 cancelled-sales-excluded-from-reports | — | advisor/015-cancelled-sales-reports |
| 2 | 019 analytics-index-usable | 015 (both edit metrics.py) | advisor/019-analytics-index-usable |
| 3 | 016 log-pii-permissions | — | advisor/016-log-pii-permissions |
| 4 | 017 money-decimal-strings | — | advisor/017-money-decimal-strings |
| 5 | 018 inventory-ledger-ui-path | — | advisor/018-inventory-ledger-ui-path |
| 6 | 020 workflow-coordinator-sad-paths | — | advisor/020-workflow-coordinator-sad-paths |

Execution mechanics: each plan runs in an isolated git worktree
(`/tmp/opencode/bi-planNNN`, branch `advisor/NNN-*`, `.venv` symlinked, venv
excluded via main `.git/info/exclude`). A fresh executor subagent implements
from the inlined plan text; the orchestrator (this session) reviews and merges.

## Implementation details (per plan)

### Plan 015 — cancelled sales excluded from reports
- `services/sale_service.py`: `AND status = 'confirmed'` in `get_total_sales`,
  `get_total_profits`, `get_sale_statistics`.
- `services/analytics/metrics.py`: `status = 'confirmed'` (or `s.status`)
  appended to all 9 date-range metric WHERE clauses.
- `services/inventory_service.py`: `s.status = 'confirmed'` in the sale union
  arm of `get_inventory_movements` and the `sales_data` CTE of
  `get_inventory_turnover`.
- `SPECIFICATIONS.md`: one line documenting the semantics.
- Sales *list* queries stay unfiltered (audit view) — out of scope by design.
- Note: `date(date) BETWEEN` rewrite is plan 019's job, NOT 015's.

### Plan 019 — analytics date-range queries index-usable
- Rewrite all 9 `date(col) BETWEEN ? AND ?` predicates to
  `col >= ? AND col < date(?, '+1 day')` (alias-aware), preserving the
  inclusive-end semantics and plan 015's status filters.
- Prove index usage via EXPLAIN QUERY PLAN probe (`SEARCH ... USING INDEX`).
- Boundary regression test (far-past dates to avoid fixture collisions).

### Plan 016 — PII out of logs; log files 0600
- `customer_service.py` / `receipt_service.py` / `product_service.py`: strip
  identifiers/search terms/SQL params from all log statements.
- `utils/system/logger.py`: chmod log files (incl. rotated backups) 0600 at
  setup, both dictConfig and fallback paths.
- PII-capture test attaches a handler to `structured_logger._logger` (NOT
  caplog — `propagate=False`).
- KNOWN DEFERRAL (resolved 2026-08-15): rotation-time hardening is setup-only
  by design — a mid-session `doRollover` recreates the active log with the
  process umask until the next startup; setup runs at every app start, and
  renames preserve 0600 on backups. Acceptable residual window; documented in
  plans/README.md row 016.

### Plan 017 — validate_money rejects fractional strings
- `validate_money` integrality via `Decimal(str(value))`; strings like
  `"999.6"` raise `ValidationException`; `"1000.0"`/`"1e3"` still accepted.
- `validate_money_multiplication` untouched (legit CLP rounding).

### Plan 018 — UI manual edits through the adjustment ledger
- `ui/inventory_view.py::edit_inventory` calls
  `adjust_inventory(product_id, data["adjustment"], reason="manual_set")`
  instead of `update_quantity`.
- `inventory_service.py` untouched (sale/purchase flows must NOT write
  adjustment rows).

### Plan 020 — workflow + coordinator sad-path tests
- New `tests/test_services/test_update_sale_workflow.py`: two-product swap
  (insufficient and sufficient stock), no-partial-writes.
- `tests/test_services/test_ux_features.py`: cache-clear failure and signal
  failure injection — coordinator swallows and continues.
- Test-only plan: `git diff --stat services/` must be empty.

## Verification (how each piece is proven)

Per plan, at minimum (run in the plan's worktree):

1. Plan-specific targeted tests — exact commands in each plan's Steps.
2. Full suite: `xvfb-run -a .venv/bin/python -m pytest -n auto -q` → all green.
   Baseline exception: `tests/test_ui/test_main_window_helpers.py` (7 tests)
   fail in this environment on base `b0dd06a` too ("unable to open database
   file" — analytics DB path unreachable locally); they are excluded from the
   pass gate ONLY if confirmed failing on base and unrelated to the plan's
   in-scope files.
3. `ruff check .`, `black --check .`, `pyright`, `bandit -q -r database services utils --skip B101` → clean.
4. Scope compliance: `git diff --stat` limited to the plan's in-scope list.

Post-merge (run in the main working tree): full suite again (`-n auto -q`
under xvfb) to catch cross-plan integration issues, then
`git push origin main`.

Review rules (orchestrator): re-run every done criterion independently, read
the full diff, audit the new tests' assertions. Undocumented deviations fail
review; documented ones are judged on merit.

## E2E test loop

The plans' regression tests land in the repo's `tests/` (the project's own
test suite — the correct home for these E2E tests). Loop: executor runs the
plan's targeted tests → orchestrator re-runs done criteria + full suite →
post-merge full suite. Every ~20 iterations (midpoint ≈ after plan 3 of 6), a
fresh sub-agent reviews `spec.md` + `todo.md` + the implementation so far for
gaps; its feedback is resolved before continuing.

## Completion definition

- All six plans DONE in `plans/README.md`; plan files moved to
  `plans/archive/` in the same change.
- `todo.md` fully checked off.
- `main` pushed with the merge history.

---

# Feature 2 — Multi-business support (CasaBea)

Requested 2026-08-15: the app must serve a second business ("CasaBea",
cinnamon-roll entrepreneurship). Deliverable: `plans/022-casabea-multi-business.md`
(planned at `3df1f6b`). Status ledger: `todo.md` → "Plan 022 (CasaBea)" section.

## Spec summary (from plan 022)

- **Architecture**: ONE SQLite DB per business, chosen at startup. All
  services/analytics/caches/UI are DB-agnostic (verified: `init_db(db_path)`
  at `database/__init__.py:84` and `DatabaseManager.initialize(path)` at
  `database/database_manager.py:35` already take a path; migrations run per
  file at `init_db`). No `business_id` column work; no High-Risk-Area changes.
- **Registry**: app config (`~/.config/billing-inventory/app_config.json`)
  gains `businesses: [{id, name, db_filename}]` + `active_business`. Absent
  registry ⇒ implicit single business "default" (backward compatible; path
  equals current `DATABASE_PATH`).
- **Bootstrap**: new `ui/business_selector_dialog.py` (Spanish) shown in
  `main.py` before `Application.initialize()`; skipped when only one
  business is configured. Switching = restart (documented constraint).
- **Backups**: `backups/<business_id>/`; `backup_service.py:52` must stop
  reading `DATABASE_PATH` directly.
- **Out of scope**: `database/`, `services/` business logic, schema,
  migrations, cross-business features (customer sync / consolidated reports).

## Verification (plan 022)

- Per phase: targeted tests — config registry tests
  (`tests/test_config.py`, `tests/test_system/test_config.py`), selector UI
  test (`tests/test_ui/` under xvfb), backup path tests, and the new
  `tests/test_services/test_business_switch.py` (real temp files: fresh DB
  born with schema; data isolation between two files; default active
  business).
- Full suite + `ruff`/`black`/`pyright`/`check_schema_drift.py` clean before
  merge; post-merge full suite in main; push; archive; mark DONE.
