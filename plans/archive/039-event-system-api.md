# Plan 039: Single attribute-based event system API; remove string registry

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- utils/system/event_system.py services/backup_service.py ui/main_window.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

`EventSystem` exposes two call styles: typed signal attributes
(`event_system.sale_added.emit(...)`, used by every service) and a string-keyed
registry (`event_system.emit_event("backup_skipped", ...)` /
`connect_to_event("sale_added", ...)`, used by backup_service and main_window).
Every signal must be registered twice (class attribute + `_signal_map` entry),
a typo in the string is a runtime `ValueError` instead of a type error, and
`clear_all_connections` depends on the map. Additionally, 4 of the 22 signals
have no emitter or listener anywhere (`app_settings_changed`,
`data_import_completed`, `data_export_completed`, `inventory_updated`). This
plan converges on the attribute API, deletes the string registry, and removes
the dead signals.

## Current state

- `utils/system/event_system.py:55-100` — 22 signal class attributes (typed,
  Qt `Signal` or `MockSignal` under headless).
- `:104-127` — `self._signal_map = {...}` duplicating every attribute.
- `:129-145` — `emit_event(name, *args)` string dispatch; unknown name → `ValueError`.
- `:147-165` — `connect_to_event(name, slot)` string dispatch.
- `:167-173` — `clear_all_connections` iterates `_signal_map`.
- `services/backup_service.py:74-80` — `event_system.emit_event("backup_skipped", {...})`.
- `services/backup_service.py:108` — `event_system.emit_event("backup_completed", str(backup_path))`.
- `ui/main_window.py:254-267` — `event_system.connect_to_event("product_added", ...)`
  etc. (14 call sites: product_added/updated/deleted, customer_added/updated/deleted,
  sale_added/updated/deleted, purchase_added/updated/deleted, inventory_changed,
  backup_skipped).
- `ui/dashboard_view.py:184-185` — already uses the attribute API:
  `event_system.backup_skipped.connect(...)`, `event_system.backup_completed.connect(...)`.
- `ui/main_window.py:238` — `self.connect_to_events()` (the method that calls
  the string API — the method name is fine, only its body changes).
- Dead signals (no emitter or listener in `services/`, `ui/`, `utils/`,
  `main.py`; grep-verified): `app_settings_changed`, `data_import_completed`,
  `data_export_completed`, `inventory_updated`.
  - `tests/test_ui/test_inventory_view.py:62` connects `inventory_updated`
    (test-only) — update or remove that connection.

**Repo conventions**:
- `USE_MOCK_EVENT_SYSTEM=1` forces the headless `MockSignal` fallback; the
  attribute API works identically under both (`Signal`/`MockSignal` both expose
  `.emit/.connect/.disconnect`).
- Tests under `tests/test_system/test_event_system.py` cover this module —
  update them to the attribute API.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Event system tests | `.venv/bin/python -m pytest tests/test_system/test_event_system.py` | all pass |
| Backup tests | `.venv/bin/python -m pytest tests/test_backup_service.py tests/test_services/test_backup_service_status.py` | all pass |
| UI tests | `.venv/bin/python -m pytest tests/test_ui/` | all pass (xvfb) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `utils/system/event_system.py`
- `services/backup_service.py`
- `ui/main_window.py`
- `tests/test_system/test_event_system.py`
- `tests/test_ui/test_inventory_view.py` (only the `inventory_updated` connection)

**Out of scope**:
- The signal payload shapes / emission sites in services (they already use
  attributes and are correct)
- `MockSignal` semantics (keep it identical)
- Adding or removing any OTHER signal

## Git workflow

- Branch: `advisor/039-event-system-api`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Convert main_window to attribute connections

In `ui/main_window.py`, rewrite the body of `connect_to_events` (:253-267) to
direct attribute calls, e.g.:

```python
event_system.product_added.connect(self.on_product_added)
event_system.product_updated.connect(self.on_product_updated)
event_system.product_deleted.connect(self.on_product_deleted)
event_system.customer_added.connect(self.on_customer_changed)
event_system.customer_updated.connect(self.on_customer_changed)
event_system.customer_deleted.connect(self.on_customer_changed)
event_system.sale_added.connect(self.on_sale_added)
event_system.sale_updated.connect(self.on_sale_changed)
event_system.sale_deleted.connect(self.on_sale_changed)
event_system.purchase_added.connect(self.on_purchase_added)
event_system.purchase_updated.connect(self.on_purchase_changed)
event_system.purchase_deleted.connect(self.on_purchase_changed)
event_system.inventory_changed.connect(self.on_inventory_changed)
event_system.backup_skipped.connect(self.on_backup_skipped)
```

Keep the method name `connect_to_events` (it is `MainWindow`'s own helper).

**Verify**: `grep -n "connect_to_event(" ui/main_window.py` → no matches.

### Step 2: Convert backup_service to attribute emits

In `services/backup_service.py`:
- `:74-80` — replace `event_system.emit_event("backup_skipped", {...})` with
  `event_system.backup_skipped.emit({...})`.
- `:108` — replace `event_system.emit_event("backup_completed", str(backup_path))`
  with `event_system.backup_completed.emit(str(backup_path))`.

**Verify**: `grep -n "emit_event(" services/backup_service.py` → no matches.

### Step 3: Delete the string registry and dead signals

In `utils/system/event_system.py`:
- Delete the dead attributes: `app_settings_changed`, `data_import_completed`,
  `data_export_completed`, `inventory_updated` (and their `_signal_map` entries).
- Delete `self._signal_map` entirely.
- Delete `emit_event` and `connect_to_event` methods.
- Rewrite `clear_all_connections` to iterate the surviving attribute signals
  directly (list them explicitly, e.g. a module-level tuple
  `ALL_SIGNALS = (event_system.product_added, ...)` or a method that
  disconnects each named attribute; simplest is an explicit list inside the method).
- Ensure `clear_all_connections` is only called with the attribute API.

**Verify**: `grep -n "emit_event\|connect_to_event\|_signal_map" utils/system/event_system.py`
→ no matches. `.venv/bin/python -m pytest tests/test_system/test_event_system.py` → pass (after updating any test that used the string API — update it to attribute calls; tests may construct `EventSystem()` directly and emit/connect via attributes).

### Step 4: Update the inventory_view test connection

In `tests/test_ui/test_inventory_view.py:62` — if it connects `inventory_updated`,
change it to a surviving signal (`inventory_changed`) or remove the connection
entirely if it only existed to exercise the removed signal.

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_inventory_view.py` → all pass.

### Step 5: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Update `tests/test_system/test_event_system.py`: replace string-API
  assertions with attribute-API assertions; remove assertions on the 4 deleted
  signals; keep the unknown-event `ValueError` test deleted (no string API to
  raise it anymore).
- No new behavior tests needed (pure consolidation); the existing backup + UI
  tests cover the wiring.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "emit_event\|connect_to_event\|_signal_map" services/ ui/ utils/ --include="*.py"` returns no matches
- [ ] `grep -n "app_settings_changed\|data_import_completed\|data_export_completed\|inventory_updated" utils/system/event_system.py` returns no matches
- [ ] `clear_all_connections` no longer references `_signal_map`
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A production emitter of `inventory_updated` or another "dead" signal exists
  that grep missed (check `grep -rn "inventory_updated" services/ ui/` before
  deleting).
- `clear_all_connections` is invoked with a signal you deleted.
- The headless `MockSignal` path fails after the edits (it must behave
  identically).

## Maintenance notes

- The event system now has one API: attribute signals. New signals: add one
  class attribute; no registry entry, no string dispatch.
- `backup_skipped`/`backup_completed` payloads are unchanged — dashboard_view
  and main_window both still connect to them; verify both fire on a skipped
  backup (test `test_services/test_backup_service_status.py`).
- `data_import_completed` was the CSV-import direction candidate's signal;
  deleting it here means the future CSV feature (if built) adds the signal back.
- Reviewer should verify `USE_MOCK_EVENT_SYSTEM=1` test runs still pass
  (CI/headless) and that no test relied on the deleted unknown-event ValueError.