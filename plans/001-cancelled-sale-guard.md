# Plan 001: Guard cancelled-sale delete/edit against double inventory restore

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
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

`cancel_sale` is the only sale mutation that guards against operating on an
already-cancelled sale. `delete_sale` and the edit path (`update_sale_workflow`)
restore inventory unconditionally, so deleting or editing a cancelled sale
restores stock a SECOND time — verified: stock 10, sell 2 (stock 8), cancel
(stock 10), delete (stock **12**). The same flow for an edit deducts stock for a
sale that is flagged cancelled. This breaks AGENTS.md's invariant "Sales
decrease inventory exactly once. Voids and sale deletions must restore inventory
exactly once" and silently inflates the ledger whenever a cancelled sale exists.

## Current state

- `services/sale_service.py:264-300` — `delete_sale`: restores inventory via
  `apply_batch_updates(items, multiplier=1.0)` inside the transaction with NO
  `status` check, then deletes `sale_items` and `sales` rows.
- `services/sale_service.py:304-309` — `cancel_sale` guards: raises
  `ValidationException(f"Sale {sale_id} is already cancelled")` when
  `sale.status == "cancelled"` (the pattern to mirror).
- `services/update_sale_workflow.py:54-102` — the edit workflow (`execute`)
  reverts old stock and re-applies new stock with no `status` check; grep for
  `status` in the file returns nothing.
- The UI renders Edit/Delete row actions for every row, including cancelled
  sales (`ui/sale_view_tables.py:120-147`, `ui/sale_view.py:1130-1149`).
- Existing invariant tests live in `tests/test_critical_backend_flows.py`
  (sale delete restores exactly once — the pattern to extend).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Tests (sale service) | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_critical_backend_flows.py -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | 286 passed, 2 skipped (pre-change baseline; count may grow) |
| Lint | `.venv/bin/ruff check .` | All checks passed |
| Format | `.venv/bin/black --check .` | all files unchanged |
| Typecheck | `.venv/bin/pyright` | 0 errors |

## Scope

**In scope**:
- `services/sale_service.py` — `delete_sale`
- `services/update_sale_workflow.py` — `execute`
- `tests/test_services/test_sale_service.py` — new regression tests
- `tests/test_critical_backend_flows.py` — new regression test (optional, if you prefer one file — pick ONE location and say so in the PR)

**Out of scope** (do NOT touch, even though they look related):
- `services/sale_service.py::cancel_sale` — already correct; leave it
- Any UI change to hide/disable buttons — the service layer must be the guard
- `models/sale.py` — no model changes
- `schema.sql`, migrations, or anything in plan 004's scope

## Git workflow

- Branch: `advisor/001-cancelled-sale-guard`
- Commit message style (matches repo): `fix: prevent double inventory restore on cancelled sale delete/edit`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Guard `delete_sale`

In `services/sale_service.py::delete_sale`, after `sale = self._require_sale(sale_id)`,
add the same guard `cancel_sale` uses:

```python
if sale.status == "cancelled":
    raise ValidationException(f"Sale {sale_id} is already cancelled")
```

`ValidationException` is already imported in this file (used by `cancel_sale`).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py -q` → all pass (existing tests must still pass — none delete cancelled sales).

### Step 2: Guard the edit workflow

In `services/update_sale_workflow.py::execute` (or wherever the workflow loads
the sale before reverting stock — read the file; it is 135 lines), add the same
check on the loaded sale's `status`. If the workflow loads the sale via a
`SaleService._require_sale`-style call, add the guard immediately after load and
before any `apply_batch_updates` call. Mirror step 1's message:
`f"Sale {sale_id} is already cancelled"`. Raise `ValidationException` (import it
if missing).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py -q` → all pass.

### Step 3: Add regression tests

In `tests/test_services/test_sale_service.py`, add two tests following the file's
existing patterns (see `test_delete_sale_restores_inventory_once` in
`tests/test_critical_backend_flows.py:60-80` for the create-sale → cancel →
delete sequence, and the `capture_signal` pattern in
`tests/test_services/test_purchase_service.py:209-277`):

1. `test_delete_cancelled_sale_raises_and_keeps_inventory` — create sale, cancel
   it, then `delete_sale` → `pytest.raises(ValidationException)`; assert
   inventory quantity is unchanged (still the restored value) and the sale row
   still exists.
2. `test_update_cancelled_sale_raises` — create sale, cancel it, then call the
   sale-update path the UI uses (find the public entry point the workflow is
   invoked through — likely `SaleService.update_sale` or similar; check
   `services/update_sale_workflow.py`'s caller) → `pytest.raises(ValidationException)`;
   assert inventory unchanged and `status` still `"cancelled"`.

Use the `db_manager` fixture (real in-memory DB) as the existing tests do.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_critical_backend_flows.py -q` → all pass, including your 2 new tests.

## Test plan

- `test_delete_cancelled_sale_raises_and_keeps_inventory` — the regression this plan fixes (double restore).
- `test_update_cancelled_sale_raises` — the edit-path twin.
- Model both on `test_critical_backend_flows.py`'s create/cancel/delete sequence.

## Done criteria

- [ ] `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_critical_backend_flows.py -q` exits 0; the 2 new tests exist and pass
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .` → All checks passed
- [ ] `.venv/bin/black --check .` → no files would be reformatted
- [ ] `.venv/bin/pyright` → 0 errors
- [ ] `grep -n "already cancelled" services/sale_service.py services/update_sale_workflow.py` → 2+ matches (delete_sale, cancel_sale, workflow)
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpts in "Current state" don't match the live code (drift).
- `update_sale_workflow.py` does not load the sale itself (e.g., the workflow
  receives the sale or relies on the caller's guard) — then the guard belongs in
  the public update entry point; verify where the sale is loaded first and put
  the guard there, and say so in the report.
- An existing test fails after the guard and the failure is not caused by a
  test that deliberately deletes/edits cancelled sales (that case means the test
  encodes the buggy behavior — update the test and note it in the report).

## Maintenance notes

- If a refund/returns flow is ever added (see plans/README.md direction
  candidates), refunds of cancelled sales must be defined explicitly — this
  guard will interact with that design.
- The UI still renders Edit/Delete on cancelled rows; the service guard turns
  those clicks into friendly errors. A follow-up could hide the buttons.
- Reviewer should confirm the guard runs BEFORE any DB mutation in both paths.
