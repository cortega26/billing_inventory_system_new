# Plan 036: Collapse customer_view twin edit/delete methods with preserved-name behavior

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- ui/customer_view.py tests/test_ui/test_customer_view.py`
> If either file changed, compare the "Current state" excerpts against the live
> code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

`CustomerView` has two near-identical edit methods and two near-identical
delete methods that have **already diverged in behavior**. The edit methods
differ on the blank-name case: `edit_customer_by_id` (used by the table's
"Editar" buttons, `customer_view.py:325`) passes `name=None` when the field is
blank, which **clears** the customer's name; `edit_customer` (used by the
context menu, `customer_view.py:619`) **reuses the old name** when blank.
The same user action therefore produces different outcomes depending on entry
point. This plan collapses each pair onto one implementation with the intended
behavior: **blank name preserves the previous name** (maintainer decision,
2026-08-17).

## Current state

`ui/customer_view.py`:
- `edit_customer_by_id(self, customer_id)` (:370-419) — re-fetches from DB,
  opens `EditCustomerDialog`, then:
  `new_name = dialog.name_input.text().strip() or None` (:393) — blank ⇒ None ⇒
  name cleared. Callers: table row buttons (`customer_view.py:325`).
- `edit_customer(self, customer)` (:493-537) — uses the passed-in Customer,
  opens dialog, then:
  `if not new_name: new_name = customer.name` (:510-511) — blank ⇒ old name kept.
  Callers: context menu (`customer_view.py:619`, `:621`), double-click (`:637`).
- `delete_customer_by_id(self, customer_id)` (:425-464) — fetches, confirms
  "¿Está seguro...", archives/restores. Caller: table row buttons (`:334`).
- `delete_customer(self, customer)` (:543-574) — same confirm flow, no refetch.
  Callers: context menu (`:621`, `:637`).

Tests that pin the current public methods (keep their names working):
`tests/test_ui/test_customer_view.py`:
- `test_edit_customer_does_not_reemit_customer_updated_event` (:81) — calls `view.edit_customer(customer)`.
- `test_delete_customer_does_not_reemit_customer_deleted_event` (:118) — calls `view.delete_customer(customer)`.
- A `FakeDialog` pattern with `mocker.patch("ui.customer_view.EditCustomerDialog", ...)` at :61.

**Repo conventions**:
- Spanish user-facing strings (match existing wording, e.g. "¿Está seguro que
  desea ...", "Cliente actualizado exitosamente.").
- UI methods decorated with `@ui_operation(show_dialog=True)` +
  `@handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)`.
- Success/error feedback via `show_info_message`/`show_error_message` from `utils/helpers`.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Customer UI tests | `.venv/bin/python -m pytest tests/test_ui/test_customer_view.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `ui/customer_view.py`
- `tests/test_ui/test_customer_view.py`

**Out of scope**:
- `services/customer_service.py` (update_customer/delete_customer/restore_customer stay as-is)
- The `EditCustomerDialog` widget
- Any other view's edit/delete twins (this plan is customer_view only)

## Git workflow

- Branch: `advisor/036-customer-view-twins`
- Commit per logical unit (`fix: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add a failing regression test for the blank-name behavior

In `tests/test_ui/test_customer_view.py`, add a test using the existing
`FakeDialog` pattern that asserts: when the dialog returns a blank name field,
`update_customer` is called with the **previous** name (not None). Model it on
`test_edit_customer_does_not_reemit_customer_updated_event` (:81) — the FakeDialog
must expose `name_input.text()` returning `""`, `identifier_9_input.text()`
returning the customer's id, and `exec()` returning True.

Run it against `edit_customer_by_id` (use a mocked `get_customer` returning the
customer). The test must FAIL on the current code (because `edit_customer_by_id`
passes `None`) — confirm the failure before proceeding.

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_customer_view.py -k blank_name` → fails on current code.

### Step 2: Make edit_customer_by_id preserve the old name on blank

In `ui/customer_view.py`, change `edit_customer_by_id` (:393) so that a blank
name reuses the fetched customer's name:

```python
new_name = dialog.name_input.text().strip()
if not new_name:
    new_name = customer.name
```

Keep the rest of the method identical (validation, update, reload, success message).

**Verify**: the new blank-name test from Step 1 now passes.

### Step 3: Make edit_customer delegate to edit_customer_by_id

Replace the body of `edit_customer(self, customer)` (:493-537) with:

```python
if customer is None:
    raise ValidationException("Ningún cliente seleccionado para editar.")
assert customer.id is not None
self.edit_customer_by_id(customer.id)
```

Delete the now-duplicated dialog/update logic. Keep the `@ui_operation` +
`@handle_exceptions` decorators on both methods.

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_customer_view.py` → all pass.

### Step 4: Make delete_customer delegate to delete_customer_by_id

Replace the body of `delete_customer(self, customer)` (:543-574) with:

```python
if customer is None:
    raise ValidationException("Ningún cliente seleccionado para eliminar.")
assert customer.id is not None
self.delete_customer_by_id(customer.id)
```

`delete_customer_by_id` already re-fetches and runs the confirm dialog — keep
its body as-is.

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_customer_view.py` → all pass.

### Step 5: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- New test: blank-name edit via `edit_customer_by_id` preserves the old name
  (Step 1; fails before the fix).
- Existing tests must keep passing: `test_edit_customer_does_not_reemit_...`,
  `test_delete_customer_does_not_reemit_...` (they call the object-based
  methods, which now delegate).
- Consider adding a twin test for the delete path through the by-id method if
  one doesn't exist (assert the confirm dialog flow archives the customer).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] The blank-name regression test exists and passes
- [ ] `edit_customer` and `delete_customer` bodies are thin delegates (grep:
  the dialog/update logic appears only once per action)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- The test at Step 1 does NOT fail on the current code (behavior already
  changed — drift; report).
- A caller outside `customer_view.py` depends on the by-id edit path CLEARING
  the name (search `edit_customer_by_id` callers — none expected outside this file).
- `assert customer.id is not None` fails in a real caller path (i.e. a caller
  passes a customer with `id=None`).

## Maintenance notes

- The behavior contract is now: **blank name on edit = keep the previous name**.
  Future callers must use the by-id methods; the object-based methods are thin
  delegates kept for the existing tests and context-menu call sites.
- Reviewer should verify the context menu (right-click → Editar/Eliminar) and
  the table buttons now behave identically, and that double-click editing
  (customer_view.py:637) still works.