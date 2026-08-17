# Plan 040: Reconcile config schema (register backup_min_free_mb, drop dead keys)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- config.py services/backup_service.py tests/test_config.py tests/test_system/test_config.py tests/test_backup_service.py`
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

The config schema and its consumers have drifted in both directions: (1)
`backup_min_free_mb` is READ by `backup_service.py:190` but absent from both
`_get_default_config()` and `_validate_config()`, so it is never validated and
its default lives only at the call site; (2) `language` defaults to `"en"` and
is validated against `["en","es"]` but is never read anywhere (the UI is
hardcoded Spanish), so the persisted config claims a bilingual capability that
doesn't exist; (3) `DebugLevel` + `DEBUG_LEVEL_MAP` (config.py:75-91) have zero
consumers. This plan registers the read-but-unregistered key and removes the
dead ceremony. (`theme` is a separate known no-op tracked in the audit backlog;
NOT in scope.)

## Current state

- `config.py:75-91` —
  ```python
  class DebugLevel(IntEnum): ...  # 5 members
  DEBUG_LEVEL_MAP: dict[DebugLevel, int] = {...}
  ```
  Grep-verified: no references outside `config.py`.
- `config.py:178-195` — `_get_default_config()` returns keys: `version`,
  `theme`, `language`, `backup_interval`, `backup_dir`, `backup_retention_days`,
  `pin_hash`, `pin_failed_attempts`, `pin_locked_until`,
  `last_backup_success`, `last_backup_skipped_time`,
  `last_backup_skipped_reason`, `businesses`, `active_business`.
  **No `backup_min_free_mb`.**
- `config.py:268-291` — `_validate_config()` requires: `version`, `theme`,
  `language`, `backup_interval`, `backup_dir`, `backup_retention_days`,
  `pin_hash`, `pin_failed_attempts`, `pin_locked_until`, `last_backup_success`,
  `last_backup_skipped_time`, `last_backup_skipped_reason`.
  **No `backup_min_free_mb`.**
- `services/backup_service.py:190` —
  `min_free_mb = config.get("backup_min_free_mb", 1024)` (and a guard at :195
  that logs and falls back to 1024 for invalid values).
- `config.py:183` — `"language": "en"` in defaults; `config.py:281` —
  `"language": (str, ["en", "es"])` in validation.
- `tests/test_backup_service.py:24` — a test patches `backup_min_free_mb`.
- `tests/test_system/test_config.py:24,56,94,101,172` — fixtures/assertions
  referencing `version`/`theme`/`language` keys (update as needed).

**Repo conventions**:
- `config.py` is a singleton with `_get_default_config()` and
  `_validate_config()` as the two schema authorities; every persisted key must
  appear in both.
- Runtime config lives in `~/.config/billing-inventory/app_config.json`
  (tests use the `isolate_config` fixture to reset the singleton per test).
- Tests: `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py tests/test_backup_service.py`.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Config tests | `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` | all pass |
| Backup tests | `.venv/bin/python -m pytest tests/test_backup_service.py tests/test_services/test_backup_service_status.py tests/test_perf_backup.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `config.py`
- `tests/test_config.py`
- `tests/test_system/test_config.py`
- `tests/test_backup_service.py` (if it constructs full-config fixtures)

**Out of scope**:
- `services/backup_service.py` (its `config.get("backup_min_free_mb", 1024)`
  call stays; the default is now consistent with the registered schema)
- The `theme` key (known no-op, tracked separately in the audit backlog)
- The `version` key (legit schema stamp; stays)
- Any behavior change to validation of the backup keys

## Git workflow

- Branch: `advisor/040-config-schema`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Remove DebugLevel and DEBUG_LEVEL_MAP

In `config.py`, delete `DebugLevel` (:75-82) and `DEBUG_LEVEL_MAP` (:85-91).
Keep `DEBUG_LEVEL = logging.INFO` (:94) and its `import logging` / `from enum
import IntEnum` imports only if still used elsewhere in the file (check; remove
the `IntEnum` import if it becomes unused).

**Verify**: `grep -rn "DebugLevel\|DEBUG_LEVEL_MAP" config.py services/ ui/ utils/ main.py` → no matches.

### Step 2: Remove the `language` key

In `config.py`: remove `"language": "en",` from `_get_default_config()` (:183)
and `"language": (str, ["en", "es"]),` from `_validate_config()` (:281).

**Verify**: `grep -n '"language"' config.py` → no matches. Update
`tests/test_system/test_config.py` fixtures/assertions that required or
asserted `language` (search `"language"` there) so the suite passes.

### Step 3: Register backup_min_free_mb in defaults and validation

In `config.py`:
- Add `"backup_min_free_mb": 1024,` to `_get_default_config()` (place it next
  to the other backup keys).
- Add `"backup_min_free_mb": (int, (1, 10240)),` to `_validate_config()`'s
  `required_keys` dict (a sane positive range; matches the semantics of the
  guard in `backup_service.py:195` which rejects non-positive values).

**Verify**: `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py tests/test_backup_service.py` → all pass.

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Existing config tests cover defaults and validation; update any that pin the
  removed `language` key.
- Add one assertion in `tests/test_config.py` (or `tests/test_system/test_config.py`)
  that the default config contains `backup_min_free_mb == 1024` and that
  `Config().get("backup_min_free_mb")` returns it without error.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "DebugLevel\|DEBUG_LEVEL_MAP" config.py services/ ui/ utils/ main.py tests/` returns no matches
- [ ] `grep -n '"language"' config.py` returns no matches
- [ ] `grep -n 'backup_min_free_mb' config.py` shows it in BOTH
      `_get_default_config` and `_validate_config`
- [ ] New default-config assertion for `backup_min_free_mb` exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- Removing the `language` key breaks a config-load path for existing
  `app_config.json` files (the validator previously required it; existing
  configs that lack it were already invalid — verify a real config parses with
  the new schema before proceeding).
- `backup_min_free_mb` validation range conflicts with a test's expectations
  (e.g. a test uses a value outside 1-10240).

## Maintenance notes

- The config schema is now: every key in `_get_default_config()` AND in
  `_validate_config()` OR it does not exist. `backup_min_free_mb` is the
  canonical default for the backup-service guard.
- `version` remains the schema stamp (bump `CONFIG_VERSION` when the schema
  shape changes — e.g. this plan changes the schema, so consider bumping it to
  `"1.1"` and noting the migration in the PR; do NOT add migration logic, just
  the stamp + test update).
- Reviewer should confirm a real config file (`~/.config/billing-inventory/app_config.json`)
  still loads and that `isolate_config`-driven tests never write it.