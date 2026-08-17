# Plan 046: Honest None-vs-raise contracts for create/get methods

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/category_service.py services/customer_service.py ui/category_management_dialog.py ui/product_view.py ui/sale_view.py ui/purchase_view.py ui/customer_view.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S-M
- **Risk**: MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The repo has two dishonest contracts that force dead code in callers:

1. **Getters**: `CategoryService.get_category` and `get_category_by_name` are
   annotated `-> Category | None` but RAISE `NotFoundException` when absent,
   while sibling getters (`ProductService.get_product`,
   `CustomerService.get_customer`, `SaleService.get_sale`) return `None`. The
   dialog's `if category: ... else: raise` branches are therefore dead code.
2. **Creators**: for a missing `lastrowid` after INSERT, four `create_*` methods
   behave differently — `create_sale` raises `DatabaseException`, `create_product`
   raises `DatabaseException`, `create_purchase` raises `ValidationException`,
   `create_customer` returns `None` (and SKIPS the audit log), `create_category`
   returns `None`. Views then write un-reachable
   `if id is not None: ... else: raise DatabaseException(...)` branches.

This plan standardizes: getters return `None`; creators raise `DatabaseException`
on missing `lastrowid`; the dead caller branches are deleted.

## Current state

- `services/category_service.py:39-48` — `get_category` raises
  `NotFoundException(f"Category with ID {category_id} not found")` with
  annotation `-> Category | None`.
- `services/category_service.py:129-138` — `get_category_by_name` raises
  `NotFoundException` with annotation `-> Category | None`.
- `services/category_service.py:17-29` — `create_category` returns
  `cursor.lastrowid` (may be `None`) with annotation `-> int | None`.
- `services/customer_service.py:27-88` — `create_customer` returns `None` when
  `lastrowid` is `None` and skips the audit log (:63 `if customer_id is not None:`).
- Reference patterns to match: `services/sale_service.py:98-99`
  (`raise DatabaseException("Failed to get new sale ID after insert.")`),
  `services/product_service.py:314-316`
  (`raise DatabaseException("Failed to create product: No product ID returned")`),
  `services/customer_service.py:169-194` / `product_service.py:55-81` (getters
  return `None`).
- Dead caller branches:
  - `ui/category_management_dialog.py:142-152` (`if category: ... else: raise
    ValidationException("Categoría ... no encontrada")`), `:171-184` (same).
  - `ui/product_view.py:421-431` (`if product_id is not None: ... else: raise
    DatabaseException("Error al agregar producto.")`).
  - `ui/sale_view.py:1019-1025` (`if sale_id: ... else: raise
    DatabaseException("Error al crear la venta")`).
  - `ui/purchase_view.py:383-388` (`if purchase_id is not None: ... else: raise
    ValidationException(...)`).
  - `ui/customer_view.py:479-484` (`if customer_id is not None: ... else: raise
    DatabaseException("Error al agregar cliente.")`).

**Repo conventions**:
- Getters return `None`; mutation preconditions use private `_require_X`
  helpers that raise `NotFoundException` (`sale_service.py:180-185`,
  `purchase_service.py:90-95`, `product_service.py:83-88`,
  `customer_service.py:220-225`).
- Creators return `int` or raise — never return `None` as a success-with-no-id.
- `DatabaseException` is the layer's uniform wrapper (matching `create_sale`).

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Category tests | `.venv/bin/python -m pytest tests/test_services/test_category_service.py tests/test_ui/test_category_management_dialog.py` | all pass |
| Customer tests | `.venv/bin/python -m pytest tests/test_services/test_customer_service.py tests/test_ui/test_customer_view.py` | all pass |
| Product/sale/purchase UI tests | `.venv/bin/python -m pytest tests/test_ui/test_product_view.py tests/test_ui/test_sale_view_helpers.py tests/test_ui/test_sale_view_tables.py` | all pass (xvfb) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `services/category_service.py`
- `services/customer_service.py`
- `ui/category_management_dialog.py`
- `ui/product_view.py`, `ui/sale_view.py`, `ui/purchase_view.py`,
  `ui/customer_view.py` (only the dead branches)
- Tests that pin the old raise/None contracts

**Out of scope**:
- `create_sale`/`create_product`/`create_purchase` bodies (already correct)
- The `_require_*` helpers (already the convergent pattern)
- Any UI message wording beyond the dead-branch deletion

## Git workflow

- Branch: `advisor/046-honest-contracts`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: category_service getters return None

In `services/category_service.py`, change `get_category` (:39-48) and
`get_category_by_name` (:129-138) to return `None` when not found instead of
raising (keep the log lines, keep the annotations — they become true):

```python
row = DatabaseManager.fetch_one(query, (category_id,))
if row:
    logger.info(...)
    return Category.from_db_row(row)
logger.warning("Category not found", extra={...})
return None
```

**Verify**: `grep -rn "raise NotFoundException" services/category_service.py` → only in
`update_category`/`delete_category` (rowcount==0 guard) — NOT in the getters.

### Step 2: category_service / customer_service creators raise on missing lastrowid

- `services/category_service.py:17-29` — after `cursor = DatabaseManager.execute_query(...)`:
  `category_id = cursor.lastrowid` then
  `if category_id is None: raise DatabaseException("Failed to get new category ID after insert.")`.
  Move the `CategoryService.clear_cache()` + emit + return after this guard.
- `services/customer_service.py:60-82` — change `if customer_id is not None:`
  to `if customer_id is None: raise DatabaseException("Failed to get new customer ID after insert.")`
  and dedent the audit + identifier logic to run unconditionally.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_category_service.py tests/test_services/test_customer_service.py` → pass.

### Step 3: Delete the dead caller branches

- `ui/category_management_dialog.py:142-152` and `:171-184` — replace
  `if category: ... else: raise ValidationException(...)` with the `if category:`
  body only (the else is now genuinely reachable only if the DB is inconsistent
  mid-operation; keep it or drop it — keep it, it is now a correct defensive
  branch, but update the message to a natural Spanish sentence if the current
  one is awkward).
- `ui/product_view.py:421-431` — replace the `if product_id is not None:
  ... else: raise` with the success body only.
- `ui/sale_view.py:1019-1025` — same.
- `ui/purchase_view.py:383-388` — same.
- `ui/customer_view.py:479-484` — same.

**Verify**: `grep -rn "Error al agregar producto\|Error al crear la venta\|Error al agregar cliente" ui/` → no matches (removed). The `if ... is not None:` else-raises are gone; each view's success flow runs directly.

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Add a sad-path test in `tests/test_services/test_category_service.py` (or
  customer_service) that mocks `DatabaseManager.execute_query` returning a
  cursor with `lastrowid = None` and asserts `DatabaseException` is raised
  (pattern: existing sad-path tests in `test_critical_backend_flows.py`).
- Add a test asserting `get_category(999999)` returns `None` (not raise) — or
  update an existing one that expected `NotFoundException`.
- Update any test that expected `create_customer`/`create_category` to return
  `None`.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "raise NotFoundException" services/category_service.py` matches only update/delete rowcount guards
- [ ] `grep -rn "Error al agregar producto\|Error al crear la venta\|Error al agregar cliente" ui/` returns no matches
- [ ] New None-lastrowid sad-path tests exist and pass
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A production caller of `get_category`/`get_category_by_name` relies on the
  raise to control flow (grep callers first — only the dialog and tests found).
- `create_customer`'s audit-log placement depends on the None branch (verify
  the dedent preserves the audit for the non-None path).
- A view's success flow has side effects that must NOT run when creation failed
  in a way the old dead-branch hid (report).

## Maintenance notes

- Contract now: getters return `None`; creators return `int` or raise
  `DatabaseException`. New services must follow this shape.
- The category dialog's defensive `else` branches are now reachable — they are
  the correct error path for an inconsistent DB; keep them.
- Reviewer should verify a manual category edit/delete against a missing
  category shows a sensible Spanish error instead of an uncaught exception.