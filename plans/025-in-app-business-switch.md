# Plan 025: In-app business switch + config registry self-healing

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 93d30f9..HEAD -- config.py ui/main_window.py ui/business_selector_dialog.py tests/test_config.py tests/test_system/test_config.py tests/test_ui/ SPECIFICATIONS.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1 (user request — twice: no in-app way to switch business)
- **Effort**: S
- **Risk**: LOW (menu action + config defaults; no persistence/DB changes)
- **Depends on**: none
- **Category**: feature
- **Planned at**: commit `93d30f9`, 2026-08-16

## Why this matters

The multi-business feature (plan 022) only lets the user switch at startup,
and the registry keys keep getting stripped by a legacy build the user
occasionally launches (`businesses`/`active_business` vanished from
`~/.config/billing-inventory/app_config.json` twice — verified). Two gaps:

1. **No in-app way to change business** — the user asked for it explicitly.
2. **No self-healing** — if the registry keys are missing when the app saves
   config, the new build preserves the stripped state and the selector stays
   hidden until the user (or an agent) re-adds the keys by hand.

This plan adds an "Archivo → Cambiar de negocio…" action (persists the choice
via the existing dialog; applied on restart per the documented constraint)
and makes the config defaults carry the registry, so every config save by the
current build re-seeds a stripped registry automatically.

## Current state

The File menu is built declaratively (`ui/main_window.py:139-150`):

```python
def setup_menu_bar(self):
    menu_bar = QMenuBar(self)
    self.setMenuBar(menu_bar)
    file_menu = self.create_menu(
        "&Archivo",
        [
            ("&Exportar Datos", "Ctrl+E", self.export_data),
            ("&Importar Datos", "Ctrl+I", self.import_data),
            ("&Crear Copia de Seguridad", None, self.backup_data),
            ("&Salir", QKeySequence.StandardKey.Quit, self.close),
        ],
    )
    ...
```

`create_menu` (`ui/main_window.py:391-403`) maps `(label, shortcut,
callback)` tuples to `QAction`s — the menu list can be built conditionally.

The selector dialog already exists and persists on accept
(`ui/business_selector_dialog.py`): `BusinessSelectorDialog.should_show()`
returns `len(config.get_businesses()) > 1`; accept calls
`config.set_active_business(id, persist=remember_checkbox)`.

The config defaults (`config.py:168-186`) do NOT include the registry:

```python
def _get_default_config(cls) -> dict[str, str | int]:
    """Return the default configuration."""
    return {
        "version": CONFIG_VERSION,
        "theme": "default",
        "language": "en",
        ...
        "last_backup_skipped_reason": "",
    }
# DEFAULT_BUSINESSES / DEFAULT_ACTIVE_BUSINESS exist at config.py:59-63
```

`_load_config` (`config.py:141-166`) merges file-over-defaults:
`merged_config = cls._get_default_config(); merged_config.update(loaded_config)`
— so adding the registry to the defaults makes it survive ANY save, and a
stripped file's next save (by current code) re-seeds it.

Info messages in the UI use the repo's `show_info_message(title, message)`
helper (imported in `ui/sale_view.py` and friends — locate its module and
mirror the import style).

Repo conventions that apply:

- All user-facing strings in Spanish.
- UI changes: `tests/test_ui/` with `qtbot`/`qapp`; run under
  `xvfb-run -a .venv/bin/python -m pytest ...`.
- Config changes: `tests/test_config.py` + `tests/test_system/test_config.py`
  both updated together (AGENTS.md).
- No SQL in `ui/`; services own workflows.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Config tests | `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` | all pass |
| UI tests | `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `config.py` — `_get_default_config` gains the registry keys; widen the return annotation to `dict[str, Any]`
- `ui/main_window.py` — File menu action (conditional on `should_show()`) + handler
- `tests/test_config.py`, `tests/test_system/test_config.py` — self-heal tests + update any default-shape assertions the change breaks
- `tests/test_ui/test_main_window.py` (or the existing main-window UI test file — check `tests/test_ui/` first and add to the closest one) — menu action tests
- `SPECIFICATIONS.md` — multi-business section: in-app switch note

**Out of scope** (do NOT touch):
- `ui/business_selector_dialog.py` — reuse as-is (persistence is inside it)
- Auto-restart on switch — NOT in this plan (DatabaseManager singleton
  lifecycle is High-Risk; the switch applies on restart, message tells the user)
- `services/`, `database/`, backup paths, schema — untouched
- The login dialog / startup flow (already wired in plan 022)

## Git workflow

- Branch: `advisor/025-in-app-business-switch`
- Commit per step; message style follows the repo (`feat: ...`, `tests: ...`, `docs: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Config defaults carry the registry (self-healing)

In `config.py`:

1. Widen the annotation: `def _get_default_config(cls) -> dict[str, Any]:`
2. Add two entries to the returned dict (after `last_backup_skipped_reason`):
   ```python
   "businesses": [dict(business) for business in DEFAULT_BUSINESSES],
   "active_business": DEFAULT_ACTIVE_BUSINESS,
   ```
   (copy the defaults — never alias the module-level list into the config
   dict, or mutations would leak).
3. Verify `_validate_config` handles the always-present keys: it validates
   `businesses` when present (it is now always present — the defaults are
   valid, so no new failure mode). Run the config test files; update any
   assertion that enumerates the default config keys or asserts the registry
   is absent from defaults (e.g. `test_legacy_config_without_registry_loads_and_keeps_defaults`
   at `tests/test_system/test_config.py:262` may need to also assert the
   registry IS present after load — that is the new intended behavior).

**Verify**: `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` → all pass.

### Step 2: The File-menu action

In `ui/main_window.py`:

1. Build the File-menu actions list conditionally:
   ```python
   file_actions = [
       ("&Exportar Datos", "Ctrl+E", self.export_data),
       ("&Importar Datos", "Ctrl+I", self.import_data),
       ("&Crear Copia de Seguridad", None, self.backup_data),
   ]
   from ui.business_selector_dialog import BusinessSelectorDialog
   if BusinessSelectorDialog.should_show():
       file_actions.append(("&Cambiar de negocio…", None, self.change_business))
   file_actions.append(("&Salir", QKeySequence.StandardKey.Quit, self.close))
   file_menu = self.create_menu("&Archivo", file_actions)
   ```
   (import at top of the file with the other imports if that matches the
   repo's style — prefer top-level imports; avoid importing inside the method
   unless a circular-import risk exists.)
2. Add the handler on `MainWindow`:
   ```python
   @ui_operation(show_dialog=True)
   def change_business(self):
       """Open the business selector; the change applies on restart."""
       from ui.business_selector_dialog import BusinessSelectorDialog

       if not BusinessSelectorDialog.should_show():
           show_info_message(
               "Información", "Solo hay un negocio configurado."
           )
           return
       selector = BusinessSelectorDialog(self)
       if selector.exec() == QDialog.DialogCode.Accepted:
           show_info_message(
               "Negocio",
               "El cambio de negocio se aplicará al reiniciar la aplicación.",
           )
   ```
   - Locate `show_info_message`'s module (used in `ui/sale_view.py` — check
     its import and mirror it) and add the import.
   - Match the repo's existing handler style (e.g. `backup_data`,
     `export_data` — check whether they use `@ui_operation(show_dialog=True)`
     and the `QDialog` import; `QDialog` is imported where needed).

**Verify**: `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` → all pass.

### Step 3: UI tests

In the closest existing main-window UI test file (check `tests/test_ui/` —
`test_main_window_helpers.py` and any main-window test; add to the most
fitting one), using the existing patterns (qtbot, config reset via the
autouse `isolate_config` fixture):

1. `test_change_business_action_present_with_two_businesses` — seed two
   businesses into the config (follow how existing tests write config keys,
   e.g. `Config.set(...)`/direct `_config` manipulation per the file's
   conventions), build `MainWindow`, assert the File menu contains
   "Cambiar de negocio".
2. `test_change_business_action_hidden_with_single_business` — default
   config (implicit default business) → action absent.
3. `test_change_business_handler_shows_restart_message` — mock
   `BusinessSelectorDialog.exec` to return `Accepted` and patch
   `show_info_message`; call `window.change_business()`; assert the message
   about restarting was shown.
4. (If the existing UI-test conventions make the dialog hard to drive, mock
   the dialog's `exec` — the persistence path is already covered by the
   config tests in plan 022's suite.)

**Verify**: `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` → all pass, including the new tests.

### Step 4: Config self-heal tests

In `tests/test_system/test_config.py` (follow `test_load_config_backfills_default_backup_settings`
at line ~98 for the temp-config-file pattern):

- `test_save_self_heals_missing_business_registry` — write a temp config file
  WITHOUT `businesses`/`active_business` (simulating the legacy-build strip),
  point Config at it (follow the file's fixture pattern for injecting a temp
  config), call `Config.set("theme", "light")` (any write), then assert the
  file now contains `businesses` with the default entry and
  `active_business == "default"`.

**Verify**: `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` → all pass.

### Step 5: Docs + full verification

1. `SPECIFICATIONS.md` multi-business section: add one line — "Cambio de
   negocio: en el arranque (selector) o desde Archivo → Cambiar de negocio;
   se aplica al reiniciar la aplicación."
2. Full verification:
   - `.venv/bin/python -m pytest` → all pass (modulo any pre-existing
     worktree UI-test exceptions in `tests/test_ui/test_main_window_helpers.py`)
   - `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean

## Test plan

| Test | File | Case |
|------|------|------|
| menu action present with 2 businesses | tests/test_ui/ (main-window file) | action in Archivo menu |
| menu action hidden with 1 business | tests/test_ui/ (main-window file) | implicit default → absent |
| handler shows restart message | tests/test_ui/ (main-window file) | accept → info message |
| save self-heals stripped registry | tests/test_system/test_config.py | missing keys re-seeded on any save |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `_get_default_config` contains `businesses` + `active_business` (grep `config.py`)
- [ ] `ui/main_window.py` has a `change_business` handler and a File-menu action appended only when `BusinessSelectorDialog.should_show()` is True
- [ ] `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` exits 0
- [ ] `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` exits 0 (modulo pre-existing worktree exceptions)
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- `show_info_message`'s module can't be located / differs from the plan's
  assumption (report what exists instead of inventing a new helper).
- The File-menu structure differs from the excerpt.
- A config test's failure reveals that `_validate_config` REJECTS the
  always-present registry (report the traceback — do not weaken validation).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- The self-healing depends on `_load_config`'s merge semantics
  (file-over-defaults) — if that merge ever changes to raw file reads, the
  heal breaks; keep the merge.
- Auto-restart on switch is deliberately out of scope: it requires
  reworking the `DatabaseManager` singleton lifecycle (High-Risk per
  AGENTS.md). The restart message is the contract.
- Reviewer scrutiny: `_get_default_config` returns copies (no aliasing), the
  action is hidden in single-business installs, and the handler's message is
  the documented restart contract.
