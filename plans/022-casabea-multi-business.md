# Plan 022: Multi-business support (CasaBea) — one DB per business, startup business selector

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 3df1f6b..HEAD -- config.py main.py database/__init__.py database/migrations.py database/database_manager.py services/backup_service.py tests/test_config.py tests/test_system/test_config.py ui/main_window.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1 (feature request — second business)
- **Effort**: M (phased: A config, B bootstrap, C backup, D docs/tests)
- **Risk**: MED (bootstrap + config + startup flow; no changes to services/analytics)
- **Depends on**: none
- **Category**: direction/feature
- **Planned at**: commit `3df1f6b`, 2026-08-15

## Why this matters

The owner needs the same app to serve a second business — "CasaBea", a
cinnamon-roll (roles de canela) entrepreneurship run by their wife. Products
are entirely different (baked goods vs. the current catalog); clients are
mostly the same building's residents today but will diverge soon. The app must
let the user pick which business they are operating at startup and keep each
business's products, inventory, sales, purchases, and reports fully isolated.

## Architecture decision (the core of this plan)

**One SQLite database file per business**, chosen at startup.

Rationale (from the codebase, verified):

- Every data access is DB-agnostic: services, the 11 analytics metrics,
  caches, and UI views all go through `DatabaseManager` / `init_db()`, which
  already accept a path (`database/__init__.py:84-87`:
  `def init_db(db_path: str | None = None)` →
  `DatabaseManager.initialize(str(db_path or DATABASE_PATH))`).
- The schema is identical per business; Alembic migrations run at every
  `init_db()` (`database/migrations.py` — runs `alembic upgrade head` on the
  active DB), so a brand-new business DB gets the full schema on first use
  with zero migration work.
- Backups, analytics, and reports are per-file by construction — no query
  changes, no cache-key changes, no touching High-Risk Areas.
- Clients diverge soon, so per-business customer tables are the correct
  long-term shape anyway (shared-customer sync can be a later feature if ever
  wanted).

Rejected alternative — shared DB with a `business_id` column: would require
scoping every query (~60 sites), every cache key, every analytics metric, and
every UI view; high regression risk across the High-Risk Areas for no current
need (no cross-business reporting is requested).

Design constraints:

- **Restart-based switching.** The business is chosen at startup; changing it
  in-app requires an app restart (documented in the UI). No runtime
  `DatabaseManager` re-initialization — avoids risky mid-session state
  changes to the connection/lock/transaction machinery.
- The existing single-business installs keep working unchanged: no
  `businesses` registry in config ⇒ implicit single business "default" using
  the current `DATABASE_PATH`.
- The global PIN login stays as-is (it protects the machine); business
  selection happens before it.

## Current state

Files and the exact seams this plan uses:

```python
# config.py:54-55
DATABASE_NAME = os.environ.get("DATABASE_NAME", "billing_inventory.db")
DATABASE_PATH = get_safe_db_path(DATABASE_NAME)
# config.py:40-48 — get_safe_db_path sanitizes the filename against traversal.

# database/__init__.py:84-87
def init_db(db_path: str | None = None):
    ...
    DatabaseManager.initialize(str(db_path or DATABASE_PATH))

# database/database_manager.py:35
def initialize(cls, db_path: str = "billing_inventory.db"):
    # creates/opens the file, chmod 0600, PRAGMAs, WAL — per-file state

# main.py:148-162 — Application.initialize(): db_already_existed = DATABASE_PATH.exists();
#   init_db(); _warn_if_active_database_looks_empty(db_already_existed) (uses DATABASE_PATH,
#   main.py:111); backup_service.start_scheduler()
# main.py:170-195 — __main__: QApplication → apply_theme → Application.initialize() →
#   LoginDialog → MainWindow

# services/backup_service.py:52 — db_path = DATABASE_PATH (the active business DB);
#   backups written to a configurable backup_dir with retention; scheduler started in main.

# config.py — Config singleton owns ~/.config/billing-inventory/app_config.json
#   (0600); defaults incl. backup_interval (config.py:165), theme (config.py:213).
```

Repo conventions that apply:

- All user-facing strings in Spanish (new dialogs must be Spanish).
- Config changes: `tests/test_config.py` + `tests/test_system/test_config.py`
  both updated together (AGENTS.md).
- UI changes: `tests/test_ui/` with `qtbot`/`qapp` fixtures; UI tests run
  under xvfb.
- No SQL in `ui/`; services own workflows; config owns app_config.json.
- pytest `--strict-markers`: any new marker must be registered in
  `pyproject.toml`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py tests/test_backup_service.py tests/test_startup_guard.py` | all pass |
| UI tests | `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |
| Schema drift | `.venv/bin/python scripts/check_schema_drift.py` | exit 0 (no schema changes in this plan, but run it) |

## Scope

**In scope**:
- `config.py` — business registry defaults, accessors, validation, backward compat
- `models/enums.py` or `models/business.py` — a `Business` value type (no DB table) and `BUSINESS_ID_PATTERN` validation constant if useful
- `main.py` — business selection before `Application.initialize()`; active-business path plumbing for `DATABASE_PATH` usage
- `ui/business_selector_dialog.py` — NEW: startup selector dialog (Spanish UI)
- `services/backup_service.py` — back up the active business DB into `backups/<business_id>/`
- `SPECIFICATIONS.md` + `readme.md` — multi-business section
- Tests: `tests/test_config.py`, `tests/test_system/test_config.py`, NEW `tests/test_services/test_business_switch.py`, `tests/test_backup_service.py`, `tests/test_ui/test_business_selector_dialog.py`

**Out of scope** (do NOT touch):
- `services/` business logic (sale/purchase/inventory/customer/analytics) — DB-agnostic by design, no changes
- `database/` — `init_db(db_path)` and `DatabaseManager.initialize(path)` already support this; no changes expected. If a change is truly needed, STOP and report.
- Any schema or migration change (the schema is identical per business)
- Cross-business features (shared customer sync, consolidated reports) — future work, not now

## Git workflow

- Branch: `advisor/022-casabea-multi-business`
- Commit per phase (A-D); message style follows the repo (`feat: ...`, `tests: ...`, `docs: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Phase A: Business registry in config (backward compatible)

In `config.py`:

1. Add a `Business` dataclass (or `TypedDict`) — put it in `models/business.py`
   (new file, no DB table; a plain value type) or at the top of `config.py`
   if simpler: fields `id: str` (e.g. `"default"`, `"casabea"`), `name: str`
   (display name, Spanish), `db_filename: str`.
2. Config defaults (only when no `businesses` key exists yet — backward
   compatibility):
   ```python
   DEFAULT_BUSINESSES = [
       {"id": "default", "name": "Principal", "db_filename": "billing_inventory.db"},
   ]
   DEFAULT_ACTIVE_BUSINESS = "default"
   ```
   Accessors: `Config.get_businesses() -> list[dict]`,
   `Config.get_active_business() -> dict`, `Config.set_active_business(id)`,
   `Config.get_business_db_path(business_id) -> Path` (uses
   `get_safe_db_path` on the filename, mirroring `DATABASE_PATH`).
3. Validation on load/save: business ids must match
   `^[a-z0-9_]+$` (safe for file/dir names); `db_filename` must be a bare
   filename (reject separators — reuse `get_safe_db_path` semantics); at
   least one business must exist; `active_business` must reference an
   existing business id (fall back to the first on mismatch, with a log).
4. `DATABASE_PATH` stays for the implicit-default path; add a helper
   `config.get_active_database_path() -> Path` that returns the active
   business's DB path (for the single-business case it equals `DATABASE_PATH`).

**Verify**:
- `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` → all pass, including new tests for: no-registry ⇒ implicit default business; registry round-trip; invalid id/filename rejected; unknown active_business falls back.

### Phase B: Bootstrap wiring + startup selector dialog

1. New `ui/business_selector_dialog.py`: a `QDialog` (Spanish) listing the
   configured businesses (radio buttons or combo), showing name + db
   filename, a "Recordar selección" checkbox (persists via
   `Config.set_active_business`), and Aceptar/Cancelar. Cancel exits the app
   (same as a failed login today). If only one business is configured, the
   dialog is skipped entirely (no UX regression for existing users).
   - Follow `ui/login_dialog.py` as the structural pattern (QDialog subclass,
     Spanish strings, styling via `ui/styles.py` DesignTokens).
2. In `main.py` `__main__` block, BEFORE `Application.initialize()`:
   ```python
   from ui.business_selector_dialog import BusinessSelectorDialog
   selector = BusinessSelectorDialog()
   if selector.exec() != QDialog.DialogCode.Accepted:
       logger.info("Application closed: no business selected")
       sys.exit(0)
   ```
   Then `Application.initialize()` uses `config.get_active_database_path()`
   everywhere it currently reads `DATABASE_PATH` (the `db_already_existed`
   check at main.py:154, `init_db()` at :155, `_build_empty_database_warning`
   at :111, and the startup-guard helpers). Keep `DATABASE_PATH` import for
   the implicit-default fallback inside the new helper.
3. `Application.initialize()` gains an optional `db_path: str | None = None`
   parameter defaulting to `config.get_active_database_path()`, so tests can
   drive it with temp paths. (Signature change only; existing callers keep
   working.)

**Verify**:
- `xvfb-run -a .venv/bin/python -m pytest tests/test_ui/test_business_selector_dialog.py` → new UI test passes (dialog shows configured businesses; single-business config skips it).
- `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` → all pass.

### Phase C: Per-business backups

In `services/backup_service.py`:

1. Replace the direct `DATABASE_PATH` use at `backup_service.py:52` with the
   active business's path (call `config.get_active_database_path()`), keeping
   the import-time default for the single-business case.
2. Backups land in `backups/<business_id>/` (create the subdir; keep the
   existing retention/scheduler logic per business). Existing single-business
   installs: keep writing to the current `backups/` root OR move to
   `backups/default/` — prefer moving to `backups/default/` for uniformity,
   and update any test asserting the old path. Restore/export paths in the UI
   that reference the backup dir must follow the same subdir.
3. Log backup events with `extra={"business_id": ...}`.

**Verify**:
- `.venv/bin/python -m pytest tests/test_backup_service.py` → all pass (update tests that assert the old backup path).
- A quick manual probe: create a temp business config, run the backup
  scheduler once, assert the file lands in `backups/<id>/`.

### Phase D: Documentation + full verification

1. `SPECIFICATIONS.md`: add a "Multi-business" section — one DB per business,
   selection at startup, restart to switch, backups per business, customers
   are per-business (no sync today).
2. `readme.md`: one paragraph on running the second business (create the
   business in the config / via the selector's management note; the DB is
   created automatically on first use).
3. New `tests/test_services/test_business_switch.py` (real temp DB files,
   not `:memory:` — the point is file isolation):
   - `test_switch_to_new_business_gets_fresh_schema`: point init_db at a
     second temp file → `init_db(path_b)` creates all tables (assert
     `customers`/`products`/`sales` exist and are empty) — proves a new
     business DB is born migrated.
   - `test_business_data_is_isolated`: create a product in business A's file;
     open business B's file; assert the product is absent; switch back; assert
     it is present.
   - `test_active_business_defaults_to_default`: no registry ⇒ active
     business is "default" and its path equals `DATABASE_PATH`.

**Verify**:
- `.venv/bin/python -m pytest tests/test_services/test_business_switch.py` → 3 passed.
- `.venv/bin/python -m pytest` → all pass (full suite).
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean.
- `.venv/bin/python scripts/check_schema_drift.py` → exit 0.

## Test plan

| Test | File | Case |
|------|------|------|
| registry defaults/round-trip/validation/fallback | tests/test_config.py, tests/test_system/test_config.py | no-registry ⇒ default; invalid ids/filenames rejected; unknown active ⇒ fallback |
| selector dialog content + skip-when-single | tests/test_ui/test_business_selector_dialog.py | two businesses shown; single business ⇒ no dialog |
| fresh business DB gets schema | tests/test_services/test_business_switch.py | init_db on new file creates all tables |
| data isolation across businesses | tests/test_services/test_business_switch.py | product in A absent in B, present back in A |
| default active business | tests/test_services/test_business_switch.py | single-business path equals DATABASE_PATH |
| per-business backup path | tests/test_backup_service.py | backup lands in backups/<business_id>/ |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `config.get_active_database_path()` exists; with no `businesses` key it equals `DATABASE_PATH` (asserted in a test)
- [ ] `ui/business_selector_dialog.py` exists; `main.py` shows it before `Application.initialize()`; single-business config skips it
- [ ] `backup_service.py:52` no longer reads `DATABASE_PATH` directly
- [ ] New-business DB files are born with the full schema (migrations run via `init_db`)
- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright`, `.venv/bin/python scripts/check_schema_drift.py` all exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- Any change to `database/` or `services/` business logic appears necessary —
  the plan's whole point is that those layers stay untouched; report the
  obstacle instead.
- `init_db(db_path)` or `DatabaseManager.initialize(path)` turn out not to be
  self-contained per path (e.g. stale global state across calls) — report
  with the failing test.
- A step's verification fails twice after a reasonable fix attempt.
- The full suite fails on tests outside the in-scope list in a way that
  implicates this plan's changes (report; don't rewrite unrelated tests).

## Maintenance notes

- Adding a third business = one entry in the config registry (or a future
  management dialog); no code changes.
- The restart-based switching decision is load-bearing: a future plan that
  wants in-app switching must rework `DatabaseManager`'s singleton lifecycle
  carefully (connection, lock, transactions, caches) — treat as High-Risk.
- Reviewer scrutiny: backward compatibility for existing installs (no
  registry ⇒ identical behavior to today, including backup paths if the
  "move to backups/default/" choice was made — verify the migration of the
  backup-path test), and that no analytics/service file was touched.
