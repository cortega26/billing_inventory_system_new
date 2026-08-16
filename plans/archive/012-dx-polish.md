# Plan 012: DX — runnable README, pre-commit install, logging paths, editorconfig

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
- **Effort**: S-M
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

Four friction points make the repo harder to work in than it needs to be:

1. **README setup is not runnable.** It says `uv pip install -r
   requirements.lock` with no `uv venv` step, never states the Python 3.13
   requirement, and its dev commands (`pytest`, `ruff check .`...) contradict
   AGENTS.md's own warning that bare `python`/`ruff` aren't on PATH here.
2. **pre-commit hooks were never installed.** `.pre-commit-config.yaml` exists
   and works (`uvx pre-commit run --all-files` passes), but no `pre-commit
   install` was ever run, so the hooks protect nothing at commit time; and the
   schema-drift check — a 2-second local guard — is not among the hooks.
3. **Logging paths are CWD-relative** while DB/config paths are
   `__file__`-relative (`config.py:51,114,158`). `utils/system/logger.py:184`
   resolves `login_config.yaml` from `Path("login_config.yaml")` and the YAML
   names log files relatively (`login_config.yaml:21,30`), with a silent
   `basicConfig` fallback (`logger.py:189-196`) when the CWD doesn't contain the
   file — logs scatter by launch directory and diagnostics become
   undiscoverable.
4. **No `.editorconfig`, and cache dirs are ignored only by the user's global
   gitignore** (`.pytest_cache/`, `.ruff_cache/` sit in the repo root and show
   up as untracked on machines without a global ignore).
5. Minor: `USE_MOCK_EVENT_SYSTEM` (`utils/system/event_system.py:8`) is an
   undocumented headless-testing affordance.

## Current state

- `readme.md:34-37` — `uv pip install -r requirements.lock` (no venv step);
  `readme.md:56-65` — bare `pytest`/`ruff`/`black`/`pyright` commands.
- `.pre-commit-config.yaml` — ruff --fix, black, trailing-whitespace,
  end-of-file-fixer, exclude for the legacy scripts (plan 011 removes them —
  remove the exclude in the same change if the files are gone).
- `.git/hooks/pre-commit` — absent; `git config core.hooksPath` — unset.
- `utils/system/logger.py:184` — `config_path = Path("login_config.yaml")`;
  `:189-196` — silent fallback.
- `login_config.yaml:21,30` — `filename: inventory_system.log` /
  `inventory_system_error.log` (relative).
- `.gitignore` — no `.pytest_cache/`, `.ruff_cache/`, `htmlcov/`.
- `utils/system/event_system.py:8` — `USE_MOCK_EVENT_SYSTEM` env check.
- `main.py:131` — `if "pytest" in sys.modules:` in production startup (the
  `_show_startup_warning` switch).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Pre-commit | `uvx pre-commit run --all-files` | all 4 hooks pass |
| Logger tests | `.venv/bin/python -m pytest tests/test_system/test_logger.py tests/test_system/test_logger_context.py -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `readme.md` — Setup/Development sections
- `.python-version` — NEW (contents: `3.13`)
- `.editorconfig` — NEW
- `.gitignore` — cache dirs
- `.pre-commit-config.yaml` — add the drift-check local hook; remove the legacy-script exclude if plan 011 removed the files
- `utils/system/logger.py` + `login_config.yaml` — path resolution
- `AGENTS.md` — document `pre-commit install` + `USE_MOCK_EVENT_SYSTEM`
- `tests/test_system/test_logger.py` — path assertions if the logger change breaks them

**Out of scope**:
- `main.py:131` (`pytest in sys.modules`) — replacing it with an env-var switch
  is tempting but touches startup behavior; note it for a follow-up, do NOT
  change it here
- Plan 013's docs reconciliation (backlog statuses etc.)
- Any change to `config.py` (already `__file__`-relative — the model to mirror)

## Git workflow

- Branch: `advisor/012-dx-polish`
- Commit messages: `docs: make readme setup runnable`, `chore: add editorconfig and python-version`, `fix: resolve log paths relative to repo root`, `chore: add schema drift check to pre-commit`
- Do NOT push unless instructed.

## Steps

### Step 1: Runnable README

Rewrite `readme.md` Setup and Development:

- Setup: `uv venv --python 3.13` then `uv pip install -r requirements.lock`
  (state the 3.13 requirement explicitly; add `.python-version` with `3.13`).
- Development: prefix commands with `.venv/bin/` — `.venv/bin/python -m pytest`,
  `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright`,
  `.venv/bin/python scripts/check_schema_drift.py`; add `pre-commit install`
  and `uvx pre-commit run --all-files`.

**Verify**: every command in the README is verifiable on this machine —
`.venv/bin/python -m pytest --help > /dev/null` etc. exit 0.

### Step 2: Editorconfig + gitignore

Create `.editorconfig` (4-space indent, utf-8, LF, for `*.py`; match the repo's
actual formatting — verify with `git show HEAD:.editorconfig 2>/dev/null` that
it does not exist). Append to `.gitignore`: `.pytest_cache/`, `.ruff_cache/`,
`htmlcov/`.

**Verify**: `git status` no longer shows `.pytest_cache/`/`.ruff_cache/`
untracked entries (they are ignored now).

### Step 3: Logging paths

In `utils/system/logger.py`, resolve `login_config.yaml` relative to the repo
root, mirroring `config.py`:

```python
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
config_path = _PROJECT_ROOT / "login_config.yaml"
```

(verify the depth: `utils/system/logger.py` → `utils/system/` → `utils/` →
repo root, so `parent.parent.parent`). Keep the fallback, but log a WARNING
when the YAML is missing instead of falling back silently.

**Verify**: run the app logger from a different CWD:
`cd /tmp && <repo>/.venv/bin/python -c "from utils.system.logger import logger; logger.info('x')"` →
log file appears in the repo root (check `ls inventory_system.log` from the
repo dir), not in `/tmp`. `.venv/bin/python -m pytest tests/test_system/test_logger.py -q` → all pass.

### Step 4: Pre-commit drift hook + install docs

Append a local hook to `.pre-commit-config.yaml`:

```yaml
  - repo: local
    hooks:
      - id: schema-drift
        name: schema drift check
        entry: .venv/bin/python scripts/check_schema_drift.py
        language: system
        pass_filenames: false
```

If plan 011 removed `file_extractor.py`/`search.py`, delete the `exclude:` line
from the config. Document `pre-commit install` in `AGENTS.md` and `readme.md`.

**Verify**: `uvx pre-commit run --all-files` → all hooks pass including
`schema-drift`. Do NOT run `pre-commit install` yourself (it writes to
`.git/hooks` — that's the operator's or the executor's call at commit time;
document it instead). If you are in an isolated worktree you may install it.

### Step 5: Document USE_MOCK_EVENT_SYSTEM

Add one line to `AGENTS.md` (Repo Notes): the `USE_MOCK_EVENT_SYSTEM` env var
forces the Qt-free mock event system for headless tests.

**Verify**: `grep -n "USE_MOCK_EVENT_SYSTEM" AGENTS.md` → match.

## Test plan

- Logger path: existing logger tests + the CWD-switch manual check in Step 3.
- No new pytest files needed.

## Done criteria

- [ ] `readme.md` Setup/Development commands all runnable with `.venv/bin/` prefixes and the `uv venv` step
- [ ] `.python-version` and `.editorconfig` exist
- [ ] `.gitignore` covers `.pytest_cache/`, `.ruff_cache/`, `htmlcov/`
- [ ] Logging from a foreign CWD writes to the repo root (manual check passed)
- [ ] `uvx pre-commit run --all-files` passes with the `schema-drift` hook
- [ ] `AGENTS.md` documents `pre-commit install` and `USE_MOCK_EVENT_SYSTEM`
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] No files outside the in-scope list are modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- The `_PROJECT_ROOT` depth guess in Step 3 resolves to the wrong directory
  (verify with a quick print before editing; correct the parent count) — only
  STOP if the logger tests break in a way that implies a design change.
- The drift-check local hook fails in pre-commit because the working tree has
  the uncommitted modernization (the drift check needs the venv — `language:
  system` uses the repo's `.venv`; if it cannot resolve, STOP and report; do
  not change the hook to a different interpreter).
- `login_config.yaml` is loaded elsewhere (grep first) — if another loader
  exists, reconcile both or STOP and report.

## Maintenance notes

- The `pytest in sys.modules` check in `main.py:131` is a known anti-pattern
  left for a follow-up; when addressed, prefer an explicit env var like
  `USE_MOCK_EVENT_SYSTEM`'s style.
- If the log directory ever moves to a user-local path (like plan 003 moves
  config), the fallback in `logger.py` must be revisited.
- Reviewer: confirm no log-path change breaks the `tests/test_system` suite on
  a foreign CWD (CI runs from the repo root, so this is a local-DX fix).
