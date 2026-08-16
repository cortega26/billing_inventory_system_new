# Plan 026: `isolate_config` teardown must never save — stop nuking the real config

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 00acf5d..HEAD -- tests/conftest.py tests/test_system/test_config.py tests/test_config.py nonexistent.json`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1 (data-loss bug: running the test suite on a dev machine wipes the user's real config)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug (test infrastructure)
- **Planned at**: commit `00acf5d`, 2026-08-16

## Why this matters

The autouse `isolate_config` fixture (tests/conftest.py) ends each test with
`Config.reset_to_defaults()` — which **saves** the config. Whenever a test
leaves `Config._config_file` unset (pointing back at the real
`~/.config/billing-inventory/app_config.json`), the teardown writes a fresh
default config over the user's real file — **wiping the PIN hash and the
business registry** (observed live on this machine at 12:55:12 during a
post-merge suite run; the PIN + registry had to be restored from backup). The
leak is caused by `Config._reset_for_testing()` called with no argument in
`tests/test_system/test_config.py:173,180` (sets `_config_file = None`). The
relative-path call at `test_config.py:97` (`Path("nonexistent.json")`)
additionally produced a stray `nonexistent.json` file in the repo root.

The teardown should reset in-memory state only — there is nothing to save.

## Current state

```python
# tests/conftest.py:51-67
@pytest.fixture(autouse=True)
def isolate_config(tmp_path):
    """Isolate configuration for each test to prevent global state pollution."""
    from config import Config

    config_file = tmp_path / "test_app_config.json"
    Config._reset_for_testing(config_file)
    Config.reset_to_defaults()          # setup: writes the TMP file — fine
    yield
    Config.reset_to_defaults()          # <-- teardown: SAVES. When
    Config._config_file = None          #     _config_file is None at this
    #                                    #     point, it writes the REAL file
```

```python
# tests/test_system/test_config.py:165-189 (the leaking tests)
def test_config_prefers_user_local_path(self, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    ...
    Config._reset_for_testing()         # bare → _config_file = None

def test_config_migrates_to_user_local_on_first_save(self, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    Config._reset_for_testing()         # bare → _config_file = None
```

`Config._reset_for_testing(config_file=None)` (config.py:463-467) sets
`cls._instance = None; cls._config = None; cls._config_file = config_file`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_system/test_config.py tests/test_config.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `tests/conftest.py` — the `isolate_config` teardown
- `tests/test_system/test_config.py` — the bare `_reset_for_testing()` calls (173, 180) and any other bare call
- `tests/test_config.py` — check line ~97 (`Path("nonexistent.json")`) and make it use `tmp_path`
- `tests/test_system/test_config.py` — new regression test
- `nonexistent.json` — delete the stray repo-root artifact (gitignored; just remove it)

**Out of scope** (do NOT touch):
- `config.py` — no production changes (the bug is in the test fixture, not Config)
- The real `~/.config/billing-inventory/app_config.json` — do not read-modify it; the reviewer restored it from backup
- Any other test file

## Git workflow

- Branch: `advisor/026-config-teardown-save-bug`
- Commit per step; message style follows the repo (`fix: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Make the teardown state-only

In `tests/conftest.py`, replace the `isolate_config` teardown so it NEVER
saves:

```python
    yield
    # State-only reset — NEVER save here: a test that left _config_file
    # unset (pointing at the real config path) would make reset_to_defaults()
    # overwrite the user's real config with defaults.
    Config._instance = None
    Config._config = None
    Config._config_file = None
```

(Keep the setup as-is: `_reset_for_testing(config_file)` + `reset_to_defaults()`
writes only the tmp file.)

**Verify**: `.venv/bin/python -m pytest tests/test_system/test_config.py tests/test_config.py` → all pass.

### Step 2: Fix the leaking calls

In `tests/test_system/test_config.py:173` and `:180`, replace the bare
`Config._reset_for_testing()` with an explicit tmp-backed file
(`Config._reset_for_testing(tmp_path / "app_config.json")` — the fixtures
already receive `tmp_path`). In `tests/test_config.py` (~line 97), replace
`Path("nonexistent.json")` with a `tmp_path`-relative file
(`tmp_path / "nonexistent.json"`), keeping the test's intent (missing file →
defaults).

**Verify**: `.venv/bin/python -m pytest tests/test_system/test_config.py tests/test_config.py` → all pass; `ls nonexistent.json` → no such file after `rm -f nonexistent.json` (Step 4).

### Step 3: Regression test

In `tests/test_system/test_config.py`, add:

```python
def test_teardown_after_leaked_config_file_never_writes_real_path(self, tmp_path, monkeypatch):
    """A test leaving _config_file unset must not make the fixture teardown
    write to the user-local config path (the 2026-08-16 data-loss bug)."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    user_local = tmp_path / ".config" / "billing-inventory" / "app_config.json"

    # Simulate the leak: bare reset leaves _config_file = None.
    Config._reset_for_testing()
    Config.reset_to_defaults()

    assert not user_local.exists()
```

(It asserts that the exact sequence that used to nuke the real config now
touches nothing outside the monkeypatched home. Place it in the same test
class as the other config tests, following their style.)

**Verify**: `.venv/bin/python -m pytest tests/test_system/test_config.py -k "teardown_after_leaked"` → 1 passed.

### Step 4: Remove the stray artifact + full verification

`rm -f nonexistent.json` (gitignored; do not commit it).

**Verify**:
- `.venv/bin/python -m pytest` → all pass (modulo any pre-existing worktree UI-test exceptions in `tests/test_ui/test_main_window_helpers.py`; 7 known)
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean
- `ls nonexistent.json` → "No existe" (not present)
- `git status` → only in-scope files

## Test plan

| Test | File | Case |
|------|------|------|
| teardown_after_leaked_config_file_never_writes_real_path | test_system/test_config.py | leaked `_config_file=None` + reset ⇒ user-local config untouched |
| (existing config tests) | test_config.py / test_system/test_config.py | still green with explicit tmp paths |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "reset_to_defaults" tests/conftest.py` shows it ONLY in the fixture setup (not the teardown)
- [ ] `rg -n "_reset_for_testing\(\)" tests/` returns nothing (no bare calls)
- [ ] `.venv/bin/python -m pytest tests/test_system/test_config.py tests/test_config.py` exits 0
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `nonexistent.json` absent from the repo root
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- Any test fails in a way that indicates the teardown change breaks a fixture
  contract (report the failing test instead of re-adding a save).
- You find ANOTHER test that writes to the real config path (report it —
  the reviewer will extend this plan).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- Future fixtures must follow the same rule: teardowns reset in-memory state,
  they never save to `_config_file`.
- The reviewer will re-run the FULL suite in the main tree after the merge
  and verify `~/.config/billing-inventory/app_config.json` (mtime + content)
  is untouched — that is the real-world proof.
- The real config was restored from `app_config.json.bak-20260816100242`
  (PIN hash + registry) — no user action needed, but the operator should
  confirm the PIN still works.
