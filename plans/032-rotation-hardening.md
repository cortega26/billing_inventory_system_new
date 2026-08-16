# Plan 032: Log rotation-time permission hardening (OwnerOnlyRotatingFileHandler)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> Touch only the files listed as in scope. If any STOP condition occurs, stop
> and report — do not improvise. When done, update the status row for this
> plan in `plans/README.md` — unless a reviewer dispatched you and told you
> they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 0b99aa5..HEAD -- utils/system/logger.py login_config.yaml tests/test_system/test_logger.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2 (backlog item — residual security window from plan 016)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `0b99aa5`, 2026-08-16 (AMENDED 2026-08-16 after a STOP)

## Why this matters

Plan 016 hardened log-file permissions (0600) but only at SETUP time; the
deferral was recorded in the backlog. A mid-session `doRollover` (10 MB × 5
rotation) recreates the active log file with the process umask (typically
0664) and leaves it world-readable until the next app start. This plan closes
that window by subclassing `RotatingFileHandler` so every rotation chmods the
new file to 0600 immediately.

## Current state

```python
# utils/system/logger.py:152-157 (setup_logger)
handler = logging.handlers.RotatingFileHandler(
    config.log_file, maxBytes=config.max_size, backupCount=config.backup_count,
    encoding="utf-8",
)
# setup_structured_logger (186-221) uses logging.config.dictConfig on login_config.yaml,
# whose two file handlers are class: logging.handlers.RotatingFileHandler
# (login_config.yaml:17-33); plus the fallback FileHandler path.
```

The plan-016 hardening (`_harden_log_file_permissions`, logger.py:189-195)
runs at setup only. Existing tests: `tests/test_system/test_logger.py` —
`test_log_files_are_owner_only`, `test_rotated_log_files_are_owner_only`
(assert the ROTATED BACKUP is 0600 — renames preserve modes; neither asserts
the fresh post-rotation active file).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_system/test_logger.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `utils/system/handlers.py` — NEW module: `OwnerOnlyRotatingFileHandler` subclass (per the amendment)
- `utils/system/logger.py` — import the subclass from `utils/system/handlers.py`; use it in `setup_logger`
- `login_config.yaml` — the two file handlers' `class:` points at `utils.system.handlers.OwnerOnlyRotatingFileHandler`
- `tests/test_system/test_logger.py` — extend the rotation test to assert the fresh active file is 0600

**Out of scope** (do NOT touch):
- The fallback `FileHandler` path (its file is created at setup and covered by the existing chmod; rotation doesn't apply there)
- Plan-016's `_harden_log_file_permissions` (keep it; it covers the initial file)
- Any other handler/logger behavior

AMENDMENT (2026-08-16, after executor STOP with verified root cause):
`dictConfig` cannot resolve `utils.system.logger.OwnerOnlyRotatingFileHandler`
because `utils/system/logger.py` initializes the module-level `logger =`
`setup_structured_logger()` DURING its own import — the `logger` attribute of
the `utils.system` package is not yet set when `resolve()` walks the dotted
path, so the class is unresolvable at exactly the moment dictConfig runs
(baseline import verified OK; failure deterministic, not worktree-only).
Fix (mechanism, verified by experiment outside the repo): put the subclass
in a SEPARATE module `utils/system/handlers.py`, which is imported from
logger.py at the top — its import completes BEFORE dictConfig runs, so the
`utils.system.handlers` attribute exists when `resolve()` walks it (and the
parent's lazy `__getattr__` does not interfere — experiment confirmed
resolution works). The YAML references
`utils.system.handlers.OwnerOnlyRotatingFileHandler`; `setup_logger` imports
the class from the new module. Scope additions: the new
`utils/system/handlers.py` file; `login_config.yaml` unchanged in spirit.

## Git workflow

- Branch: `advisor/032-rotation-hardening`
- Commit per step; message style follows the repo (`sec: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: The subclass in its own module

Create `utils/system/handlers.py`:

```python
import logging
import logging.handlers
import os
from contextlib import suppress


class OwnerOnlyRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that keeps log files owner-only (0600) across rotations."""

    def doRollover(self) -> None:
        super().doRollover()
        with suppress(OSError):
            os.chmod(self.baseFilename, 0o600)
```

In `utils/system/logger.py`: import the class at the top
(`from utils.system.handlers import OwnerOnlyRotatingFileHandler`) and use it
in `setup_logger` (replace the `RotatingFileHandler` construction).

In `login_config.yaml`, point the two file handlers at the new module (which
finishes importing before dictConfig runs — the amendment's verified fix):

```yaml
    file_handler:
        class: utils.system.handlers.OwnerOnlyRotatingFileHandler
        ...
    error_file_handler:
        class: utils.system.handlers.OwnerOnlyRotatingFileHandler
        ...
```

Do NOT reference `utils.system.logger.OwnerOnlyRotatingFileHandler` anywhere
(the unresolvable path).

**Verify**: `.venv/bin/python -m pytest tests/test_system/test_logger.py` → all pass.

### Step 2: Extend the rotation test

In `tests/test_system/test_logger.py`, extend
`test_rotated_log_files_are_owner_only` (or add a sibling) to also assert
that the FRESH active file created by the rotation is 0600 — i.e., after
`rotate_logs(logger_test_dir)`, `os.stat(logger_test_dir / "app.log").st_mode & 0o777 == 0o600`.
(Follow the existing test's fixture usage: `configured_logger`,
`logger_test_dir`, `_flush_logs`.)

**Verify**: `.venv/bin/python -m pytest tests/test_system/test_logger.py -k "rotated"` → passed.

### Step 3: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass (modulo pre-existing worktree UI exceptions)
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean

## Test plan

| Test | File | Case |
|------|------|------|
| rotated backup stays 0600 | test_logger.py (existing) | unchanged |
| fresh active file after rotation is 0600 | test_logger.py (extended) | the plan-016 gap closed |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `OwnerOnlyRotatingFileHandler` defined in `utils/system/handlers.py` with the `doRollover` chmod
- [ ] `login_config.yaml`'s two file handlers use `utils.system.handlers.OwnerOnlyRotatingFileHandler`; `setup_logger` uses the imported class
- [ ] `python -c "from utils.system.logger import logger"` imports cleanly (module-level init + dictConfig resolve)
- [ ] `rg -n "RotatingFileHandler" utils/system/logger.py login_config.yaml` shows no plain `logging.handlers.RotatingFileHandler` left in the file-handler paths
- [ ] `.venv/bin/python -m pytest tests/test_system/test_logger.py` exits 0 with the extended assertion
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- dictConfig can't resolve the dotted handler class (report the error).
- The rotation test's existing fixture doesn't produce a fresh active file
  after rotation (report what it produces instead).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- This closes the plan-016 deferral; the backlog item is resolved.
- Future handler changes must keep the owner-only property (0600) — the
  subclass is the single place.
- Reviewer scrutiny: the subclass is used on BOTH the dictConfig and
  setup_logger paths; the fallback FileHandler path stays as-is by design.
