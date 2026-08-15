# Plan 014: Extend pyright scope into ui/ incrementally

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

- **Priority**: P3
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

`pyrightconfig.json` scopes type checking to the backend
(`config.py`, `main.py`, `database`, `models`, `services`, `utils`,
`scripts/check_schema_drift.py`) and excludes `ui/` and `tests/`. Measured on
the working tree: `pyright ui` reports **58 errors** (ui/sale_view.py: 15,
ui/purchase_view.py: 9, ui/product_view.py: 8, ui/customer_view.py: 7,
ui/login_dialog.py: 6, main_window.py: 4) and `pyright tests` reports **91
errors**. The excluded code is the worst-typed in the repo — and it is the
money-adjacent, highest-churn surface (sale/purchase/product views). Real
`reportOptionalMemberAccess`-class failures live there (e.g.,
`ui/sale_view_tables.py:79` — `strftime` on a possibly-None date) that would
crash at runtime.

The exclusion was a defensible scope decision (PySide6/Qt typing noise), but it
should be a documented milestone, not a permanent wall. This plan extends the
scope incrementally — file by file — keeping the enforced baseline at zero
errors at every step.

## Current state

- `pyrightconfig.json` — `include: [config.py, main.py, database, models,
  services, utils, scripts/check_schema_drift.py]`; `exclude: [**/__pycache__,
  **/.venv]`; `typeCheckingMode: basic`.
- `ui/sale_view.py` — 15 errors; `ui/purchase_view.py` — 9; `ui/product_view.py`
  — 8; `ui/customer_view.py` — 7; `ui/login_dialog.py` — 6; `ui/main_window.py`
  — 4; the rest scattered.
- `ui/sale_view_tables.py:79` — example error class:
  `self.date.strftime(...)`-style `reportOptionalMemberAccess` (verify the
  exact line when editing).
- `tests/` — 91 errors (incl. `tests/utils/base_test.py:29,31`); plan 008
  removes the duplicate return at `base_test.py:39-41`, which may clear some.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Scoped check | `.venv/bin/pyright` | 0 errors, 7 warnings (baseline) |
| UI check | `.venv/bin/pyright ui` | 0 errors after each file lands in scope |
| Tests | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format | `.venv/bin/ruff check .` / `.venv/bin/black --check .` | clean / clean |

## Scope

**In scope**:
- `pyrightconfig.json` — include list grows one entry at a time
- `ui/*.py` — the files being brought into scope (annotations/guards only)
- `tests/` — NOT in scope for type checking (see Maintenance notes)
- `AGENTS.md` — update the pyright scope line as the include list grows

**Out of scope**:
- Behavior changes — annotations, `assert`s, and narrowings only
- PySide6 stub workarounds beyond what the noise floor requires
- `tests/` type checking (91 errors, mostly mock-heavy code with no runtime
  value in fixing; revisit only if a future plan needs it)

## Git workflow

- Branch: `advisor/014-pyright-ui`
- Commit messages: `type: bring ui/login_dialog.py into pyright scope`, `type: bring ui/sale_view.py into pyright scope`, ...
- Do NOT push unless instructed.

## Steps

### Step 1: Establish the per-file error inventory

Run `.venv/bin/pyright ui` and save the full report. Group errors by file and
by RULE (`reportOptionalMemberAccess`, `reportArgumentType`, etc. — pyright
suffixes). This is the work plan.

**Verify**: the report is saved; the counts match the audit's (~58 total).

### Step 2: Bring in the easy files first

Add to `pyrightconfig.json` include, in this order (fewest/cheapest errors
first — reorder if your Step 1 report disagrees, and say why):

1. `ui/login_dialog.py` (6 errors — likely `hash_pin`/dialog typing)
2. `ui/main_window.py` (4 errors)
3. `ui/customer_view.py` (7 errors)

For each: fix the errors with annotations/asserts ONLY (e.g., Optional guards
before `.strftime`, explicit types on Qt widget attributes). Match the style
used in the backend fixes: prefer narrowing guards over `# type: ignore`
except where PySide6 typing makes the ignore the honest answer (then use
`# pyright: ignore[<rule>]` with no vague bare ignores). Run
`.venv/bin/pyright` after each file — the include list only grows when the
file is clean.

**Verify**: after each file, `.venv/bin/pyright` → 0 errors, warnings count
unchanged (7) or explained.

### Step 3: The big files

Bring in `ui/product_view.py` (8), then `ui/purchase_view.py` (9), then
`ui/sale_view.py` (15). Same rule: fix until `.venv/bin/pyright` reports 0
errors with the file in scope, then keep it in scope. For sale_view's
`strftime`-on-None class of error, prefer the same
`if x is not None else ""` guard style already used in
`services/receipt_service.py` and `models/sale.py`.

**Verify**: `.venv/bin/pyright` → 0 errors after each file; `.venv/bin/python
-m pytest tests/test_ui -q` → all pass after each file (UI tests exercise the
typed paths).

### Step 4: Remaining ui files

Add the remaining `ui/*.py` files one at a time (whatever Step 1 found). If a
file's error count is dominated by one PySide6-stub class of false positives
(>50% of its errors from one rule like `reportAttributeAccessIssue` on Signal
or Qt enums), you may use a file-level
`# pyright: ignore[<rule>]` comment at the top of that file — but only per-rule,
and record it. Do not ignore whole files.

**Verify**: `.venv/bin/pyright ui` → 0 errors; `.venv/bin/pyright` → 0 errors.

### Step 5: Document

Update `AGENTS.md`'s pyright line: scope now includes `ui/`; `tests/` remains
excluded (mock-heavy, 91 errors, no runtime value). Record any per-file
`# pyright: ignore` entries and why.

**Verify**: `grep -n "ui/" AGENTS.md` → the updated scope line.

## Test plan

- No new tests. The UI test suite is the behavior gate per file
  (`.venv/bin/python -m pytest tests/test_ui -q`).

## Done criteria

- [ ] `.venv/bin/pyright` → 0 errors, 7 warnings (the `utils/__init__.py`
      lazy-import warnings are intentional — leave them)
- [ ] `.venv/bin/pyright ui` → 0 errors
- [ ] `pyrightconfig.json` include contains `ui` (or all ui files)
- [ ] `.venv/bin/python -m pytest tests/test_ui -q` and `.venv/bin/python -m pytest -q` both exit 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .` clean
- [ ] No behavior changes: `git diff` on `ui/` shows annotations/guards only (spot-check)
- [ ] `AGENTS.md` documents the new scope and the `tests/` exclusion rationale
- [ ] `plans/README.md` status row updated

## STOP conditions

- A file's error count grows between steps (fixes shouldn't introduce new
  errors) — STOP and report which file.
- A fix requires a behavior change to type-clean (e.g., a genuinely broken
  Optional path you'd have to alter at runtime) — write a failing test for the
  behavior, then STOP and report; do not silently change runtime behavior.
- `tests/test_ui` fails after a file lands in scope — STOP and report; revert
  that file from the include list.

## Maintenance notes

- `tests/` stays excluded: the 91 errors are concentrated in mock-heavy
  fixtures (`tests/utils/base_test.py`) with no runtime risk. If the test
  suite ever grows real integration fixtures, revisit.
- PySide6 signal typing (`Any`-annotated in `utils/system/event_system.py`)
  means signal access in ui/ stays loose — that is the accepted noise floor.
- Plan 011's dead-code sweep may delete UI-referenced methods; run 014 after
  011 to avoid typing dead code.
- Reviewer: the diff should read like the backend pyright fix session —
  annotations and guards, zero runtime changes.
