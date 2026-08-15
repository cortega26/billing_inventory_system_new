# Plan 003: PIN security — rotate, relocate config, PBKDF2, persistent lockout

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

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `7453aee`, 2026-08-15

## SECRETS HANDLING (read before anything else)

A live PIN hash is committed in `app_config.json` (tracked at HEAD). **Do not
copy the hash value into any file you write** — plans, diffs, or commit
messages. Reference it as "the `pin_hash` value in `app_config.json`" only.
The operator must rotate the PIN after this lands (a burned hash cannot be
un-burned).

## Why this matters

The PIN gate is the app's only access control, and it is weak in four stacked
ways:

1. **The hash is committed to git** (`app_config.json` is tracked; the hash is
   a 64-char SHA-256 digest at HEAD). Anyone with repo access can crack a 4-6
   digit PIN offline in seconds (see 2) and the secret survives in history even
   after deletion.
2. **The hashing is single-round SHA-256 with a hardcoded global salt**
   (`ui/login_dialog.py:18-21`): `sha256(b"billing_inventory_system_salt_2026" + pin)`.
   The salt is a compile-time constant shared by every install; one precomputed
   table cracks every install. Effective keyspace: 10^4–10^6.
3. **No persistent brute-force lockout** (`ui/login_dialog.py:30-31,165-177`):
   the 5-attempt counter lives on the dialog instance; `main.py:186-189` exits
   the process, so restarting grants 5 fresh attempts instantly.
4. **Runtime config (including the PIN hash) lives in the repo tree and is
   world-readable** (mode `-rw-rw-r--`); the financial ledger DB, WAL, and
   backups are `-rw-r--r--` (world-readable).

This plan: relocate runtime config out of the repo, rotate + harden the hash,
persist the lockout, and restrict file permissions. It also fixes the
"forgotten PIN" operational dead-end (DIRECTION-06) by documenting reset.

## Current state

- `ui/login_dialog.py:18-21`:
  ```python
  def hash_pin(pin: str) -> str:
      """Hash the PIN with a hardcoded salt."""
      salt = b"billing_inventory_system_salt_2026"
      return hashlib.sha256(salt + pin.encode("utf-8")).hexdigest()
  ```
- `ui/login_dialog.py:145-177` — setup path calls `config.set("pin_hash", hashed)`;
  verification is `if hashed == self.pin_hash`; `self.attempts` incremented per
  dialog instance, `self.max_attempts = 5`, rejection on `>=` (then
  `main.py:187` `sys.exit`).
- `config.py:108-134` — `_load_config` uses `cls._config_file or
  (Path(__file__).parent / "app_config.json")`; `config.py:158-161`
  `_save_config` writes in place. `Config._reset_for_testing(config_file)`
  exists for tests (`tests/conftest.py:50-67` — autouse `isolate_config`).
- `tests/test_config.py` and `tests/test_system/test_config.py` — pin current
  config behavior; the autouse `isolate_config` fixture isolates per test.
- `main.py:186-189` — on login rejection the app exits; there is no reset path.
- File modes: observed on disk — `billing_inventory.db` and backups
  `-rw-r--r--`, `app_config.json` `-rw-rw-r--`. No `chmod`/`umask` anywhere.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Config tests | `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py -q` | all pass |
| Login tests | `.venv/bin/python -m pytest tests/test_ui/test_login_dialog.py -q` | all pass (xvfb/display needed — use `xvfb-run` if no display) |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |
| Drift check (unaffected, sanity) | `.venv/bin/python scripts/check_schema_drift.py` | passed |

## Scope

**In scope**:
- `ui/login_dialog.py` — `hash_pin`, verification, lockout
- `config.py` — config file location + file permissions
- `tests/test_config.py`, `tests/test_system/test_config.py`, `tests/test_ui/test_login_dialog.py`
- `.gitignore` — runtime config entry
- `readme.md` or `SPECIFICATIONS.md` — operator PIN setup/reset note (one short section)
- `AGENTS.md` — one line noting config relocation, if it describes config paths

**Out of scope** (do NOT touch):
- `main.py` — no changes (the exit-on-lockout behavior stays; the lockout is now persistent)
- `services/backup_service.py`, `database/database_manager.py` — file-permission helper may be called from config only; do not restructure backups
- Git history rewriting (`git filter-repo`/BFG) — document it as a follow-up for the owner; do NOT force-push anything yourself
- `app_config.json` content beyond what relocation requires

## Git workflow

- Branch: `advisor/003-pin-security`
- Commit messages: `sec: relocate runtime config out of repo`, `sec: harden PIN hashing with PBKDF2`, `sec: persist login lockout across restarts`, `sec: restrict config file permissions`
- Do NOT push unless instructed.

## Steps

### Step 1: Relocate the runtime config out of the repo tree

In `config.py`, change the config file resolution so it prefers a user-local
path and falls back to the repo copy (backward compatibility with existing
installs):

- Primary: `Path.home() / ".config" / "billing-inventory" / "app_config.json"` (create the directory on save).
- Fallback: if the primary does not exist AND the repo copy
  (`Path(__file__).parent / "app_config.json"`) exists, load the repo copy (and
  migrate it: copy to primary on first successful save).
- `_reset_for_testing` keeps working (tests pass an explicit `_config_file`).

Keep `DATABASE_PATH` and backup paths as-is (out of scope).

Update `tests/test_config.py` if any test asserts the repo-relative path;
instead add a test asserting the user-local path is used when `_config_file`
is not injected.

**Verify**: `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py -q` → all pass. `.venv/bin/python -c "from config import Config; Config._reset_for_testing(); print(Config.get('backup_interval'))"` → `24` (defaults work without any file).

### Step 2: Harden the PIN hash

In `ui/login_dialog.py`:

- Replace `hash_pin` with PBKDF2: `hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 600_000)` where `salt` is a fresh `os.urandom(16)` **per install**, generated on first PIN setup and stored next to the hash.
- New stored format: `pbkdf2$600000$<salt_hex>$<digest_hex>`.
- On PIN setup (the `if not self.pin_hash:` branch), generate the salt, store the new-format hash, and delete any legacy hash.
- On verification: if the stored hash is legacy format (plain 64-hex), reject with a clear message telling the operator to re-set the PIN (or migrate on first successful legacy verification — pick ONE behavior, prefer reject-with-message, and say so in the report). Compare with `hmac.compare_digest`.
- Do NOT write the salt or hash constants into tests in a way that reproduces real values — test with a throwaway salt.

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_login_dialog.py -q` (needs display; else `xvfb-run -a`) → all pass. Existing tests that assert the old hash format must be updated to the new format (that is expected).

### Step 3: Persistent lockout

Persist failed-attempt state in the config:

- Keys: `pin_failed_attempts` (int) and `pin_locked_until` (ISO timestamp or empty string) — add to `config.py::_get_default_config` and `_validate_config` (validate types).
- In `LoginDialog`: on failure increment and save; when `attempts >= max_attempts`, set `pin_locked_until = now + lockout_window` (use 5 minutes) and save; on verification, if `pin_locked_until` is in the future, show the remaining wait and reject WITHOUT incrementing; on success, reset both keys.
- `main.py` exit-on-reject stays; the lockout survives the restart because it is persisted.

**Verify**: add a test in `tests/test_ui/test_login_dialog.py` (or `tests/test_system/test_config.py` for the config side): simulate 5 failures, assert `pin_locked_until` is set; simulate a new dialog instance, assert verification is blocked until the window passes (inject a past `pin_locked_until` to test the expiry branch).

### Step 4: Restrict file permissions

Add a small helper in `config.py` (e.g. `_restrict_permissions(path)`) that applies `os.chmod(path, 0o600)`; call it after `_save_config` writes. Also call it for the DB and backups — the cleanest single hook is a shared helper; since `database_manager.py` and `backup_service.py` are out of scope for structural changes, do this: call the helper in `config.py` for the config file, and ADD a one-line `os.chmod(path, 0o600)` after connection init in `database/database_manager.py::initialize` (the connection's DB file) and after backup file creation in `services/backup_service.py` — these are single-line permission calls, not restructuring. If either file's structure makes this awkward, STOP and report instead of refactoring.

**Verify**: create a temp config via `Config._reset_for_testing(tmp)`, save, assert `stat.S_IMODE(path.stat().st_mode) == 0o600`. Manual check on the real DB file after `init_db()` in a scratch copy only.

### Step 5: Rotation + docs

- Document in `readme.md` (one short "Seguridad" section): first-launch PIN setup; forgotten PIN → delete the `pin_hash` key from the user-local config file (path printed in the section) to re-arm first-run setup.
- Add to `AGENTS.md` (Repo Notes or a guardrail line): runtime config now lives outside the repo; `app_config.json` in the repo is a default template only.
- **Rotation note (owner action, not code)**: after this lands, the operator must set a new PIN so the burned hash stops working. State this in the PR description.

**Verify**: `grep -rn "billing_inventory_system_salt_2026" ui/ services/ config.py` → no matches. `git status` shows no `app_config.json` content change staged beyond `git rm --cached` + `.gitignore` (see Step 6).

### Step 6: Untrack the runtime config

- Add `app_config.json` to `.gitignore`.
- `git rm --cached app_config.json` (keeps the file on disk).
- Do NOT rewrite history. Add a note in the PR: history purge (BFG/filter-repo) + force-push is the owner's call if the repo is shared.

**Verify**: `git status` shows `app_config.json` as deleted-from-index only; the file still exists on disk.

## Test plan

- Update: any login test asserting the old SHA-256 format or the per-instance counter.
- New: config relocation test (user-local path preferred, repo fallback migrates); PBKDF2 round-trip (set → verify ok, wrong pin → reject); legacy-hash rejection path; persistent lockout (fail 5× → locked; new instance blocked; expiry via injected past timestamp); permissions test (config file mode 0600).
- Patterns: `tests/test_config.py` + `tests/test_ui/test_login_dialog.py` are the exemplars.

## Done criteria

- [ ] `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py tests/test_ui/test_login_dialog.py -q` exits 0 with the new tests
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] `grep -rn "billing_inventory_system_salt_2026" ui/ config.py services/` → no matches
- [ ] `git ls-files app_config.json` → empty (untracked); file still on disk
- [ ] `.gitignore` contains `app_config.json`
- [ ] Config file mode is 0600 after save (test asserted)
- [ ] No PIN hash value appears in any committed file or test
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any existing test cannot be updated without changing its intent (they pin
  legitimately-changed behavior — updating format expectations is expected;
  STOP if a test pins behavior you cannot explain).
- The user-local config path conflicts with `Config._reset_for_testing` in a way
  that breaks the autouse `isolate_config` fixture — STOP and report; do not
  weaken the fixture.
- Permission changes break the schema drift check or backup tests — STOP and
  report (the drift check opens the DB read-only; perms should not matter, but
  verify).

## Maintenance notes

- The legacy-hash rejection path is a one-time migration cost; it can be removed
  after one release.
- If the app ever grows multi-user or remote access, this PIN scheme is still
  insufficient (no OS-level account); the plan assumes the single-operator
  threat model.
- Reviewer: confirm no test writes a real-looking hash (throwaway salts only).
