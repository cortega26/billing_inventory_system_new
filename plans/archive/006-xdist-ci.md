# Plan 006: Fix the xdist crash and enable parallel CI; bump CI action versions

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
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

AGENTS.md records "the UI tests crash workers under `-n auto` (Qt); keep CI
serial" — a symptom, not a cause. The root cause is one order-dependent test:
`tests/test_ui/test_sale_view_tables.py::test_update_sale_total_label_uses_clp_rounding`
builds a bare `QLabel()` without requesting pytest-qt's `qtbot`/`qapp` fixture,
so when it runs in a process where no QApplication exists it dies with
`Fatal Python error: Aborted`. Reproduced in all three modes: isolated run →
hard crash; `pytest -n auto` → 1 worker crash (flaky-looking, order-dependent);
serial suite → passes only because another test created the app first.

Fixing this unlocks parallel CI (`-n auto`) — measured 10.96s serial vs 6.6s
parallel on the current suite — and removes a confusing order-dependent failure.
While in CI, bump the deprecated action versions (`actions/checkout@v3` runs on
Node 16, `setup-python@v4`, community `GabrielBB/xvfb-action@v1`) and fix the
pip cache key to include `requirements.lock` (it currently keys on
`requirements.txt` ranges, so it never invalidates on lockfile changes).

## Current state

- `tests/test_ui/test_sale_view_tables.py:47-48`:
  ```python
  def test_update_sale_total_label_uses_clp_rounding():
      total_label = QLabel()
      update_sale_total_label(...)
  ```
  (no `qtbot` parameter — the only test in the suite that touches Qt widgets
  without a fixture).
- `tests/conftest.py` — has autouse fixtures (`setup_test_environment`,
  `isolate_config`, `clear_test_data`, `clean_logs`) but no autouse Qt app
  fixture; pytest-qt's app is session-scoped and only created when requested.
- `.github/workflows/ci.yml:17` — `actions/checkout@v3`; `:20` —
  `actions/setup-python@v4`; `:48` — `GabrielBB/xvfb-action@v1`; `:23` —
  `cache: 'pip'` (keys on requirements.txt/pyproject.toml, not the lockfile);
  `:50` — `run: pytest` (serial).
- `plans/README.md` — this plan gates the `-n auto` direction note.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| The crashing test, isolated | `.venv/bin/python -m pytest tests/test_ui/test_sale_view_tables.py::test_update_sale_total_label_uses_clp_rounding -q` | passes (after fix); currently aborts |
| Parallel suite | `.venv/bin/python -m pytest -q -n auto` | all pass, no worker crash |
| Serial suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `tests/test_ui/test_sale_view_tables.py` — add `qtbot` fixture to the test
- `tests/conftest.py` — OPTIONAL: autouse fixture that guarantees a QApplication
  exists for any test that touches Qt (see Step 1 decision)
- `.github/workflows/ci.yml` — action bumps, cache key, `-n auto`
- `AGENTS.md` — remove/replace the "UI tests crash workers" line with the fixed reality

**Out of scope**:
- Any change to `pytest.ini`-equivalent addopts in `pyproject.toml`
- xdist config knobs beyond `-n auto`
- pytest-randomly behavior

## Git workflow

- Branch: `advisor/006-xdist-ci`
- Commit messages: `fix(test): request qtbot fixture to avoid Qt crash under xdist`, `ci: enable parallel pytest, bump action versions, fix cache key`
- Do NOT push unless instructed.

## Steps

### Step 1: Fix the crashing test

Add `qtbot` as a parameter to `test_update_sale_total_label_uses_clp_rounding`.
Check the file's imports and the `update_sale_total_label` signature first (the
function may take the label and rows — the fix is ONLY the fixture).

Decision point (choose the minimal option that works, state it in the report):
- (a) `qtbot` on that one test, OR
- (b) a `tests/conftest.py` autouse fixture that imports `QApplication` and
  creates/attaches one if none exists (guards any future test that forgets).

Prefer (a) if the one-test fix makes `-n auto` green; use (b) only if another
hidden case surfaces (then STOP and report it first — do not blanket-create an
autouse app silently).

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_sale_view_tables.py::test_update_sale_total_label_uses_clp_rounding -q` → 1 passed (no abort).

### Step 2: Prove parallel stability

Run the full suite with `-n auto` FIVE times. All five must pass with zero
worker crashes. Record the timing (serial vs parallel).

**Verify**: 5x `-n auto` green; note the fastest serial run for comparison.

### Step 3: Update CI

- `actions/checkout@v3` → `actions/checkout@v4`
- `actions/setup-python@v4` → `actions/setup-python@v5`
- Keep `GabrielBB/xvfb-action@v1` ONLY if the xvfb-run step still works after
  the bump (it is unmaintained; if `xvfb-run -a .venv/bin/python -m pytest`
  works under the new setup-python, replace the action with a plain
  `xvfb-run` step — verify locally with `xvfb-run -a .venv/bin/python -m pytest tests/test_ui -q`).
- Add to setup-python: `cache-dependency-path: requirements.lock`
- Test step: `run: pytest -n auto`

**Verify**: workflow YAML parses (`.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` → no error).

### Step 4: Update AGENTS.md

Replace the line about UI tests crashing workers under `-n auto` with: CI runs
`pytest -n auto` under xvfb; the Qt crash that forced serial mode is fixed
(plan 006).

**Verify**: `grep -n "crash workers" AGENTS.md` → no matches.

## Test plan

- No new tests needed beyond the fixture fix; the five `-n auto` runs ARE the
  verification (they exercise every test in random order across workers).

## Done criteria

- [ ] The isolated crashing test passes (Step 1)
- [ ] 5 consecutive `pytest -n auto` runs pass with no worker crash
- [ ] CI uses `pytest -n auto`, `actions/checkout@v4`, `actions/setup-python@v5`, `cache-dependency-path: requirements.lock`
- [ ] `AGENTS.md` no longer claims UI tests crash workers
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .` clean
- [ ] No files outside the in-scope list are modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any of the five `-n auto` runs crashes a worker — STOP and report which test
  (the fix is incomplete; do not switch CI to parallel anyway).
- `xvfb-run` replacement breaks UI tests locally — revert to the action and
  note it; do not ship a broken CI leg.
- The test file's structure differs from the excerpt (function renamed/moved) —
  locate the equivalent test and apply the fixture there.

## Maintenance notes

- New UI tests must request `qtbot`/`qapp` (or the conftest guard from option
  (b) must exist) — the parallel CI now depends on it.
- If the suite grows past ~5 minutes serial, revisit `-n 2`/`-n 4` tuning; the
  crash fix makes it safe to tune.
- Reviewer: confirm CI ran green on a PR before merging (you cannot run GitHub
  Actions locally).
