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

# Feature 3 — Seed CasaBea with El Rincón's customers (plan 023)

Requested 2026-08-16: copy El Rincón de Ébano's 127 customers into CasaBea as
a one-time seed. Architecture decision confirmed with the owner: keep
per-business DBs; copy identity data only; a future one-way refresh reuses
the same script; bidirectional sync explicitly out of scope. Deliverable:
`plans/023-copy-customers-between-businesses.md` (planned at `17f9640`).

## Spec summary

- New headless CLI `scripts/copy_customers.py` (mirrors the
  `scripts/check_schema_drift.py` pattern): `--source` (default: business
  "default"), `--target` (default: business "casabea"), `--include-inactive`,
  `--dry-run`. Spanish messages.
- Importable `copy_customers(source_path, target_path, ...) -> dict[str, int]`
  ({inserted, existing, invalid}): plain sqlite3, parameterized SQL, single
  transaction on target; validates via `validate_9digit_identifier` /
  `validate_3or4digit_identifier`; never overwrites existing identifier_9;
  identity-only copy (the repo schema has NO balance/credit columns — the
  live DB's `current_balance`/`credit_limit` are a drift finding, see
  plans/README backlog); invalid rows are counted, not fatal.
- Tests: `tests/test_scripts/test_copy_customers.py` (6 cases, real temp
  files). No changes to services/ui/config/database.

## Verification (plan 023)

- `--help` exits 0; the 6 tests pass; full suite green (modulo pre-existing
  worktree UI exceptions); ruff/black/pyright clean.
- Real-run boundary: executing against the production DBs (El Rincón → a
  fresh casabea.db) requires the operator's explicit approval; first run with
  `--dry-run`.

# Feature 4 — Reconcile customer schema drift (plan 024)

Requested 2026-08-16: reconcile the `customers.current_balance` /
`customers.credit_limit` drift found by plan 023. Decision (confirmed):
ADD the columns to the repo schema sources (`models/customer.py`,
`schema.sql`, new Alembic revision) matching the live DB exactly — zero data
risk (all live rows at defaults); the migration must be a no-op on the live
DB (inspector-guarded). Rejected: dropping from the live DB (destroys legacy
lineage). Deliverable: `plans/024-customer-credit-columns.md` (planned at
`131c2d7`).

## Spec summary

- Model: `current_balance: int = Field(default=0, sa_column=...server_default
  "0")`, `credit_limit: int = Field(default=50000, ...server_default "50000")`
  + `check_customer_credit_limit` in `__table_args__` (no CHECK on balance —
  live DB has none). No validation/from_db_row changes.
- schema.sql: the two columns, matching live DDL.
- Migration: `down_revision = "72e1091bcd50"`, inspector-guarded add/drop
  (no-op on live; additive on fresh). Real downgrade (repo first).
- Tests: fresh-DB defaults + CHECK; no-op on already-migrated DB (live
  simulation); additive on pre-024 DB; model defaults.
- Out of scope: `identifier_9 COLLATE NOCASE` + name-length CHECK drift
  (backlog note), services/ui/config/copy script, live DB itself.

## Verification (plan 024)

- `check_schema_drift.py` exit 0; 3 migration tests + model test pass; full
  suite green (modulo pre-existing worktree UI exceptions); ruff/black/pyright
  clean. Post-merge: manual app boot on the live DB to confirm the no-op.

# Feature 5 — In-app business switch + config self-healing (plan 025)

Requested 2026-08-16 (user twice: no in-app way to switch business). Two parts:

## Spec summary

1. **In-app switch**: `ui/main_window.py` "&Archivo" menu gains "&Cambiar de
   negocio…" (only when >1 business configured, mirroring
   `BusinessSelectorDialog.should_show()`). Handler opens the existing
   `BusinessSelectorDialog` (persistence already inside it), then shows the
   info message "El cambio de negocio se aplicará al reiniciar la aplicación"
   via the repo's `show_info_message` helper. No auto-restart (documented
   constraint; DatabaseManager lifecycle is High-Risk).
2. **Config self-healing**: `_get_default_config()` in `config.py` gains
   `"businesses": [dict(b) for b in DEFAULT_BUSINESSES]` and
   `"active_business": DEFAULT_ACTIVE_BUSINESS` (widen the return annotation
   to `dict[str, Any]`). Because `_load_config` merges file-over-defaults,
   any config written by the current build now ALWAYS contains the registry —
   a stripped config (e.g. by a legacy build) self-heals on the next save.
3. Tests: config self-heal (load stripped file → `Config.set(...)` → file
   re-seeded); menu action present/absent by business count; click opens
   dialog; accept → info message. SPECIFICATIONS.md multi-business section
   updated.

## Verification (plan 025)

- Config test files green (existing "defaults" assertions updated to the new
  shape); UI tests under xvfb; full suite; ruff/black/pyright. Post-merge:
  manual launch — selector at startup + Archivo → Cambiar de negocio works.

# Bugfix 6 — isolate_config teardown nukes the real config (plan 026)

Found 2026-08-16 while verifying plan 025 post-merge: the autouse
`isolate_config` fixture's teardown calls `Config.reset_to_defaults()`, which
SAVES. Any test that leaves `_config_file = None` (e.g.
`tests/test_system/test_config.py:173,180` call `_reset_for_testing()` bare)
makes the teardown write defaults to the REAL
`~/.config/billing-inventory/app_config.json` — wiping the PIN hash and the
business registry on the dev machine (verified: it happened at 12:55:12
during the post-merge suite run; config restored from backup). The relative
`Path("nonexistent.json")` at `test_config.py:97` produces the stray
repo-root `nonexistent.json`.

Fix: the teardown must reset in-memory state ONLY (no save) — replace
`Config.reset_to_defaults()` with a state-only reset; fix the bare
`_reset_for_testing()` calls; add a regression test (monkeypatched home,
`_config_file=None` left behind ⇒ user-local config untouched); remove the
stray `nonexistent.json`. Planned at `00acf5d`.

# Feature 7 — Per-business dashboard KPI profiles (plan 027)

Requested 2026-08-16: "Valor Inventario" makes sense for a reseller
(El Rincón) but not for a value-added producer (casabea.cl bakery). Design:
a per-business `dashboard` field in the registry (`"reseller"` default |
`"production"`), the dashboard composes its MetricWidget cards from the
active business's profile. "Valor agregado" ≈ existing Ganancia Total
(revenue − ingredient cost) — no new economic metrics; the profile just
emphasizes margin % and units for production. Planned at commit `ad20acc`.

## Spec summary

- `config.py`: `dashboard` field validated against
  {"reseller", "production"} (missing → "reseller" via `.get` default);
  `DEFAULT_BUSINESSES` entries gain the field.
- `ui/dashboard_view.py`: extract the top-row card set per profile —
  reseller: Ventas Totales, Ganancia Total, Valor Inventario, Margen
  Ganancia, Ventas de Hoy (unchanged); production: Ventas Totales, Ganancia
  Total, Margen Ganancia, Unidades Vendidas, Ventas de Hoy. Low-stock block
  and charts stay for both. New `get_total_units_sold` method using the
  dashboard's date range.
- `services/sale_service.py`: new `get_total_units_sold(start, end)`
  mirroring `get_total_sales` (JOIN sale_items, `status='confirmed'` filter
  per plan 015, range-validated).
- Tests: config validation (unknown value rejected, missing → reseller);
  sale_service units sum + cancelled exclusion; NEW
  `tests/test_ui/test_dashboard_view.py` (qtbot): reseller shows Valor
  Inventario and not Unidades Vendidas; production the inverse.
- SPECIFICATIONS.md: dashboard-profiles section.

## Verification (plan 027)

- Config + sale-service + new dashboard UI tests pass (xvfb); full suite
  green (modulo known worktree UI exceptions); ruff/black/pyright clean.
- Post-merge: set `"dashboard": "production"` on casabea in the real config
  and eyeball the card row (user action).

# Bugfix 8 — Codacy SQL-injection warnings on scripts/ + test (plan 028)

Requested 2026-08-16. Six CRITICAL Codacy findings on `f"PRAGMA ...({table})"`
/ `f"SELECT COUNT(*) FROM {table}"` sites. All interpolate INTERNAL constants
(hardcoded tuples, SQLModel.metadata, dict keys) — no user input; false
positives, but treatable: 4 PRAGMA sites convert to SQLite's table-valued
functions (`SELECT * FROM pragma_table_info(?)` / `pragma_index_list(?)`,
bound parameter, no f-string); 2 COUNT sites can't bind identifiers →
documented `# nosec B608` (repo convention per AGENTS.md; note: bandit's
scope excludes scripts/, Codacy covers it). Planned at `44c2fa5`.

## Spec summary

- `scripts/check_schema_drift.py` (2 sites): bound pragma functions.
- `scripts/check_legacy_upgrade.py` (3 sites): 2 bound pragma functions +
  1 nosec B608 with comment (COUNT typeof query).
- `tests/test_services/test_business_switch.py:72` (1 site): nosec B608 +
  comment (closed test tuple).
- Verification: scripts still behave identically (drift check exit 0;
  legacy-upgrade tests green); full suite; ruff/black/pyright.

## Verification (plan 028)

- `grep -rn 'f"PRAGMA\|f"SELECT COUNT' scripts/ tests/` → only the nosec
  sites remain; `check_schema_drift.py` exit 0; `pytest tests/test_database`
  (legacy upgrade tests) green; full suite; ruff/black/pyright clean.

# Feature 9/10 — Dead-code sweep + duplication consolidation (plans 029/030)

Requested 2026-08-16 (focused audit). 33 fully-dead symbols (single
occurrence repo-wide, zero in tests — verified via occurrence-count scan:
definition + zero other hits, plan 011 protocol) + 15 test-only (compliant
with AGENTS.md, kept). Duplication: `_get_product_ids` ×3 (byte-identical),
sale-item hydration ×2 in sale_service (+1 divergent purchase variant,
documented separate), receipt text builders ×2 in sale_view, scan sound ×2
(wrapper vs raw QSoundEffect). Planned at `3c74057`.

## Spec summary

- **029**: delete the 33 dead symbols + orphaned imports (ruff F401); keep
  test-only tier; zero-reference grep guard per symbol; full suite.
- **030**: `utils/helpers.get_product_ids_from_items` shared by
  sale/purchase/coordinator; one `_hydrate_sale_items` helper in
  sale_service used by both list methods; one `_build_receipt_text` in
  sale_view (view_sale + preview share it); purchase_view uses the
  `SoundEffect` wrapper (drop raw QSoundEffect).

## Verification

- 029: `rg <name>` → 0 hits for all 33; suite green; ruff/black/pyright.
- 030: behavior pinned by existing tests (get_all_sales, receipt UI tests);
  suite green; ruff/black/pyright.

# Backlog round — plans 031/032/033

- **031**: `get_inventory_movements` invisible same-day adjustments —
  root cause: adjustment rows stamped `CURRENT_TIMESTAMP` (UTC) + the three
  union arms use date-only `BETWEEN`. Fix: store LOCAL time
  (`datetime('now','localtime')` at the 2 INSERT sites) + range-shift query
  (plan-019 pattern) on all three arms. Historical UTC rows keep their
  stored value (documented).
- **032**: log rotation-time hardening — `OwnerOnlyRotatingFileHandler`
  (chmod 0600 in `doRollover`) registered in `login_config.yaml` + used by
  `setup_logger`; covers the gap plan 016 deferred.
- **033**: expose `LowStockMetric`/`InventoryAgingMetric` via
  `AnalyticsService` wrappers; dashboard low-stock switches to the wrapper
  (single implementation; read-only contract).
- Decisions on older backlog items: `identifier_9 COLLATE NOCASE` —
  REJECTED (identifiers are digits; no case semantics); name-length CHECK —
  folded into the schema-alignment check inside plan 031's verification
  (verify schema.sql already carries it; if not, add it). `identifier_3or4`
  NOT NULL — tooling note already honored (copy script); closed as
  documented.
