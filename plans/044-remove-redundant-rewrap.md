# Plan 044: Remove catch-log-re-wrap inside decorator-covered service methods

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/sale_service.py services/customer_service.py services/product_service.py services/category_service.py services/inventory_service.py services/backup_service.py services/audit_service.py services/mutation_coordinator.py services/receipt_service.py services/analytics/engine.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: 020 (sad-path characterization tests exist and pin these flows)
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

~20 service methods are decorated with `@db_operation` + `@handle_exceptions`
which already log failures and re-raise, yet their bodies ALSO wrap everything
in `try: ... except Exception: log; raise DatabaseException(...)`. Result:
every DB failure in a mutation method is logged 2-3 times with
`DatabaseException("Query failed: ...")` nested inside a NEW
`DatabaseException("Failed to create sale: ...")` — a same-type wrap that adds
ceremony and noise with zero semantic value. The inner handler's only real job
(normalizing unexpected programmer errors like `KeyError`) is better served by
letting them propagate loudly. This plan deletes the redundant inner handlers
from the service layer.

## Current state

Verified at commit `d560e43`:

- `services/sale_service.py` — `create_sale` (:154-158, re-raises
  Validation/NotFound, wraps rest in `DatabaseException`), `get_all_sales`
  (:210-229), `delete_sale` (:260-291), `cancel_sale` (:309-337).
- `services/customer_service.py` — ~6 sites (e.g. :83-88, :247-249, :314-318,
  :345-352, :379-386, :465-469) — same shape.
- `services/product_service.py` — ~6 sites (e.g. :44-51, :110-112, :156-161,
  :193-200, :230-237, :301-303).
- `services/category_service.py` — 3 sites (:30-34, :80-85, :100-105) — these
  ALSO wrap `NotFoundException`/`ValidationException` into `DatabaseException`
  (a known anti-pattern per the audit; the wrap is redundant since the
  decorators already catch NotFoundException).
- `services/inventory_service.py` — `apply_batch_updates` (:51-61, wraps
  unexpected types into `ValidationException`), `get_all_inventory` (:195-214).
- `services/backup_service.py` (6), `services/audit_service.py` (2),
  `services/mutation_coordinator.py` (3), `services/receipt_service.py` (1),
  `services/analytics/engine.py` (:73-75, log + bare `raise`).

The decorators (`utils/decorators.py`): `handle_exceptions(*types,
show_dialog)` catches the listed types, logs once via `log_exception`, shows a
dialog (optional), re-raises. `db_operation` = `handle_exceptions(DatabaseException,
NotFoundException, ...)`. `DatabaseManager` helpers already raise
`DatabaseException` on SQL failures — so the inner re-wrap is always a
same-type wrap of a value the decorator is about to handle anyway.

**Behavior preservation requirement**: tests from plans 008/020 assert the
error MESSAGE text (`"Failed to create sale: ..."` etc.) and that the
exceptions are `ValidationException`/`DatabaseException`/`NotFoundException`.
Deleting the inner wrap changes the message text and the log count. Update the
tests that pin message text to the new (shorter) propagation behavior — the
exception TYPE for known failures stays the same because DatabaseManager raises
DatabaseException and validators raise ValidationException, and the decorators
re-raise them untouched.

**Repo conventions**:
- Services raise `DatabaseException`/`ValidationException`/`NotFoundException`;
  the decorators normalize logging/dialog.
- Log messages should be one record per failure.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Sale sad-path tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_update_sale_workflow.py tests/test_critical_backend_flows.py` | all pass (after message updates) |
| Customer/product/category/inventory tests | `.venv/bin/python -m pytest tests/test_services/test_customer_service.py tests/test_services/test_product_service.py tests/test_services/test_inventory_service.py tests/test_services/test_analytics_service.py tests/test_services/test_receipt_service.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Security | `.venv/bin/bandit -q -r database services utils --skip B101` | exit 0 |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**: the service-layer sites listed above (sale, customer, product,
category, inventory, backup, audit, mutation_coordinator, receipt, analytics
engine).

**Out of scope**:
- UI-layer handlers (`ui/*_view.py`) — same anti-pattern, but each needs
  per-view decorator-coverage review; tracked as a maintenance follow-up.
- `services/purchase_service.py` and `services/purchase_query_service.py` —
  they have NO inner try/except (verified); do not add any.
- Changing the decorators' semantics.

## Git workflow

- Branch: `advisor/044-remove-redundant-rewrap`
- Commit per logical unit (one per service, or grouped).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Audit the exact sites

Run `grep -rn "except Exception" services/` and list every site. For each,
decide:
- If the method is decorated with `@db_operation`/`@handle_exceptions` and the
  inner block ONLY re-raises known types and wraps the rest in
  `DatabaseException`/`ValidationException`: **delete the inner try/except**
  entirely, keeping the method body's functional lines.
- If the inner block does something more (e.g. builds audit data, conditionally
  emits), keep those lines, delete only the wrapping.

**Verify**: produce the site list in your working notes; after Step 2, every
site on the list has no inner `except Exception` left.

### Step 2: Delete the redundant wrappers (service by service)

For each method identified:
1. Remove the `try:` / `except Exception as e: ... raise ... from e` block.
2. Dedent the body back to the method level.
3. Ensure `logger.error` inside the removed block is gone (the decorator logs).
4. Keep `DatabaseManager.transaction()` boundaries and `with` blocks intact.
5. For `category_service.py` (wraps NotFound/Validation into DatabaseException):
   remove the wrap too — the decorators already catch `NotFoundException` and
   `ValidationException` on those methods (`@handle_exceptions(ValidationException,
   DatabaseException, ...)` / `(NotFoundException, DatabaseException, ...)`).

Run the full targeted suite after EACH service file and update tests that pin
removed message text:
- Search `tests/` for the old messages (`"Failed to create sale: "`,
  `"Failed to delete sale: "`, `"Failed to fetch sales: "`,
  `"Failed to fetch inventory: "`, `"Failed to update category: "`, etc.) and
  update them to assert the new propagated message or the exception TYPE only.
- If a test asserts a DOUBLE-wrapped chain (`DatabaseException` whose `str`
  contains the inner message), simplify it to assert the single message.

**Verify**: targeted suite for that service passes; `grep -rn "except Exception" <file>` shows no inner handler remains.

### Step 3: Analytics engine + audit/backup/coordinator sites

- `services/analytics/engine.py:73-75` — `except Exception: logger.error; raise`
  logs then re-raises the same exception the caller handles. Delete the
  try/except (the caller decorator logs). If a caller relies on the log line,
  verify the caller's decorator logs it instead.
- `services/audit_service.py`, `services/backup_service.py`,
  `services/mutation_coordinator.py` — apply the same rule; for
  `mutation_coordinator` (per-step defensive try/excepts), KEEP the per-signal
  catch that prevents one bad signal from killing the sequence — only remove
  blocks that re-wrap a single operation with no additional logic.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_backup_service_status.py tests/test_system/test_logger.py tests/test_critical_backend_flows.py` → pass.

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/bandit -q -r database services utils --skip B101`
→ exit 0; `.venv/bin/ruff check .` → exit 0; `.venv/bin/black --check .` → exit 0;
`.venv/bin/pyright` → exit 0. Then grep: `grep -rn "Failed to create sale\|Failed to delete sale\|Failed to fetch sales\|Failed to fetch inventory" tests/ services/` → only test assertions you deliberately kept.

## Test plan

- Update sad-path tests that pinned the wrapped messages (list them as you
  find them; the plan-008/020 tests are the main suspects).
- Add one test asserting that a failing DB write is logged exactly once (use
  the `caplog` fixture on a service method that fails; pattern:
  `tests/test_services/test_purchase_service.py` if it logs) — this pins the
  anti-double-logging behavior.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "except Exception" services/` shows no remaining redundant
      wrappers (only the intentionally-kept per-signal catches in
      `mutation_coordinator.py` if you kept them)
- [ ] `grep -rn "Failed to create sale\|Failed to delete sale\|Failed to fetch sales\|Failed to fetch inventory\|Failed to update category" services/` returns no matches
- [ ] New single-log regression test exists and passes
- [ ] `.venv/bin/bandit -q -r database services utils --skip B101` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- Deleting an inner wrapper changes the exception TYPE for a KNOWN failure
  (e.g. a test expects `DatabaseException` and it becomes a raw `KeyError`) —
  that signals the inner block was doing real normalization; report the site
  instead of deleting it.
- A service method's body has logic INSIDE the `try` that must run on the
  failure path (e.g. cleanup) — preserve it or report.
- A test's failure text expectation reflects behavior you cannot reproduce
  after the change.

## Maintenance notes

- Error handling in services is now: validators/services raise the right
  exception type; decorators log once + optionally show the dialog. New
  mutation methods should NOT wrap bodies in try/except (follow the plan-044
  shape).
- The UI-layer re-wrap sites are the known remaining instance of this pattern —
  tracked as a follow-up; they need per-view decorator-coverage review.
- Reviewer should spot-check the log volume for a failing sale creation (one
  record expected) and that the user-facing dialog still appears.