# Plan 018: Route manual UI inventory edits through the adjustment ledger

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat b0dd06a..HEAD -- ui/inventory_view.py services/inventory_service.py tests/test_services/test_inventory_service.py tests/test_ui`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `b0dd06a`, 2026-08-15

## Why this matters

`get_inventory_movements` (inventory_service.py:343) is the app's documented
"Virtual Ledger" verification tool. But the only inventory write path the UI
actually uses — the manual +/- adjustment dialog — calls
`InventoryService.update_quantity`, which never writes an
`inventory_adjustments` row. The two methods that DO write the ledger
(`set_quantity`, `adjust_inventory`) have zero production callers. Result: the
movement history silently omits every manual stock change made from the UI —
the most common adjustment path — so stock reconciliations against the ledger
can't see manual edits at all.

## Current state

The UI edit path (`ui/inventory_view.py:271-281`):

```python
@ui_operation(show_dialog=True)
@handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
def edit_inventory(self, item: dict[str, Any]):
    dialog = EditInventoryDialog(item, self)
    if dialog.exec():
        data = dialog.get_data()
        if data["adjustment"] != 0:
            self.inventory_service.update_quantity(
                product_id=item["product_id"],
                quantity_change=data["adjustment"],
            )
            self.load_inventory()
            show_info_message("Éxito", "Inventario actualizado correctamente")
```

The dialog's `adjustment` is a signed delta (`ui/inventory_view.py:53-57`:
`QDoubleSpinBox`, min -1000000, max 1000000, 3 decimals; `get_data()` returns
`adjustment = self.adjustment_input.value()`).

The three write paths in `services/inventory_service.py`:

```python
# :88-131  update_quantity(product_id, quantity_change, emit_events=True)
#   - used by sales/purchases via apply_batch_updates AND by the UI dialog
#   - does NOT write inventory_adjustments (correct for sale/purchase flows:
#     those are represented by their own union arms in get_inventory_movements)

# :218-253  set_quantity(product_id, new_quantity)
#   - sets an absolute value; writes adjustment row reason="manual_set" + audit
#   - zero production callers (test-only)

# :294-332  adjust_inventory(product_id, quantity_change, reason)
#   - applies a signed delta inside a transaction; writes adjustment row with
#     the given reason + audit; clears cache + emits inventory_changed AFTER commit
#   - zero production callers (test-only)
```

The ledger query (`:351-368`) reads `inventory_adjustments` for
`'adjustment'`-type rows and joins sale_items/purchases for the others — so
manual edits made via `update_quantity` never appear.

Semantics: `adjust_inventory` matches the dialog exactly — signed delta,
transactional, raises `ValidationException` if the result would be negative,
and has the same event/cache post-commit behavior as `update_quantity` with
`emit_events=True` (both clear cache + emit `inventory_changed`). Existing
tests already pin `adjust_inventory`'s ledger behavior:
`tests/test_services/test_inventory_service.py:176-204`
(`test_adjust_inventory_happy_path`, `test_adjust_inventory_below_zero_raises_and_leaves_no_trace`).

Repo conventions that apply:

- UI must not implement persistence rules — it calls the service; the service
  owns the ledger. Moving the UI call from `update_quantity` to
  `adjust_inventory` respects this.
- Service methods are the enforcement boundary (AGENTS.md).
- `tests/test_services/test_inventory_service.py` uses the real-DB
  `db_manager` fixture with a module setup creating `self.prod_id`
  (lines ~90-106) and helpers `_quantity()` / `_adjustment_rows()`
  (lines 108-115).
- UI tests live in `tests/test_ui/` and need `qtbot`/`qapp` fixtures.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` | all pass |
| UI tests | `.venv/bin/python -m pytest tests/test_ui` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |
| Security | `.venv/bin/bandit -q -r database services utils --skip B101` | exit 0 |

## Scope

**In scope**:
- `ui/inventory_view.py` — the `edit_inventory` call site only
- `tests/test_services/test_inventory_service.py` — ledger-coverage test for the UI path
- `tests/test_ui/` — update any test that asserts `update_quantity` is called by `edit_inventory` (grep first, see Step 1)

**Out of scope** (do NOT touch):
- `services/inventory_service.py` — `update_quantity` must NOT learn to write
  `inventory_adjustments`: sales and purchases call it via
  `apply_batch_updates` and would double-record movements (their movements are
  already derived from `sale_items`/`purchase_items`). `set_quantity` /
  `adjust_inventory` stay as-is.
- `ui/inventory_view.py` barcode/edit dialog behavior beyond the one call.
- Any change to `get_inventory_movements` or its `reason` strings.

## Git workflow

- Branch: `advisor/018-inventory-ledger-ui-path`
- Commit per step; message style follows the repo (`fix: ...`, `tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Survey UI-test expectations

Grep the test tree for assertions about the manual edit path:
`rg -n "update_quantity|edit_inventory|EditInventoryDialog" tests/test_ui/`
If a UI test asserts `inventory_service.update_quantity` is called from the
inventory view, note it — Step 2 will require updating it to expect
`adjust_inventory`.

**Verify**: you can list the affected tests (may be none).

### Step 2: Switch the UI call to `adjust_inventory`

In `ui/inventory_view.py:277-280`, replace:

```python
self.inventory_service.update_quantity(
    product_id=item["product_id"],
    quantity_change=data["adjustment"],
)
```

with:

```python
self.inventory_service.adjust_inventory(
    product_id=item["product_id"],
    quantity_change=data["adjustment"],
    reason="manual_set",
)
```

Notes:
- `reason="manual_set"` matches the reason `set_quantity` already uses
  (`inventory_service.py:233`), keeping the ledger vocabulary consistent.
- The `if data["adjustment"] != 0` guard stays as-is (a 0 delta should not
  create a ledger row; `adjust_inventory` with 0 would write one — the guard
  already prevents it).
- No other changes to `edit_inventory` (dialog, load_inventory refresh, info
  message all stay).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` → all pass.

### Step 3: Update or add UI-test expectations

If Step 1 found UI tests asserting the old call, update them to expect
`adjust_inventory` (match their mocking style — likely
`mocker.patch("services.inventory_service.InventoryService.adjust_inventory")`
or patching on the view's service instance). If no UI test covers the edit
path, add one in the existing inventory UI test file that drives
`edit_inventory` and asserts the adjustment row is written (follow the
closest existing UI test for fixtures; if a full dialog test is impractical,
assert at the service boundary as in Step 4 and leave the UI path covered by
the existing dialog tests).

**Verify**: `.venv/bin/python -m pytest tests/test_ui` → all pass.

### Step 4: Add a ledger-coverage regression test (service level)

In `tests/test_services/test_inventory_service.py`, add (inside the same test
class, reusing `self.prod_id`, `_quantity()`, `_adjustment_rows()`):

```python
def test_ui_manual_edit_path_writes_movement_and_audit_rows(self):
    # Simulates exactly what ui/inventory_view.edit_inventory does today.
    self.inventory_service.adjust_inventory(self.prod_id, 5.0, "manual_set")

    assert self._quantity() == 5.0
    rows = self._adjustment_rows()
    assert len(rows) == 1
    assert rows[0]["quantity_change"] == 5.0
    assert rows[0]["reason"] == "manual_set"

    movements = self.inventory_service.get_inventory_movements(
        self.prod_id, "2000-01-01", "2100-01-01"
    )
    assert any(m["type"] == "adjustment" for m in movements)

def test_ui_manual_edit_negative_below_zero_raises_and_leaves_no_ledger_row(self):
    self.inventory_service.adjust_inventory(self.prod_id, 5.0, "manual_set")
    with pytest.raises(ValidationException, match="cannot be negative"):
        self.inventory_service.adjust_inventory(self.prod_id, -999.0, "manual_set")
    assert self._quantity() == 5.0
    assert len(self._adjustment_rows()) == 1
```

(The second test re-pins the no-partial-writes behavior for the UI path's
exact call signature.)

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py -k "manual_edit"` → 2 passed.

### Step 5: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0
- `.venv/bin/bandit -q -r database services utils --skip B101` → exit 0

## Test plan

| Test | File | Case |
|------|------|------|
| test_ui_manual_edit_path_writes_movement_and_audit_rows | test_inventory_service.py | adjust with reason "manual_set" → quantity changed, ledger row with same reason, appears in get_inventory_movements |
| test_ui_manual_edit_negative_below_zero_raises_and_leaves_no_ledger_row | test_inventory_service.py | negative-to-zero result → ValidationException, no partial writes |
| (updated UI test if any) | tests/test_ui/ | view calls adjust_inventory, not update_quantity |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `rg -n "update_quantity" ui/inventory_view.py` returns nothing
- [ ] `rg -n "adjust_inventory" ui/inventory_view.py` shows exactly one call with `reason="manual_set"`
- [ ] `services/inventory_service.py` is byte-identical before/after (`git diff --stat services/inventory_service.py` empty)
- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts.
- A UI test's failure reveals that `edit_inventory` relies on `update_quantity`
  in a way `adjust_inventory` doesn't provide (e.g. creating a missing
  inventory row — the dialog only edits existing rows, so this shouldn't
  happen; if it does, report).
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (especially
  `services/inventory_service.py`).

## Maintenance notes

- Future inventory write paths should prefer `adjust_inventory`/`set_quantity`
  when the change is a manual or audit-relevant adjustment, and
  `update_quantity` only for sale/purchase flow (which derive their own
  ledger rows).
- The `reason` vocabulary is now `"manual_set"` (set_quantity + this plan) and
  free-form for `adjust_inventory` callers; a future plan could centralize it
  in `models/enums.py`.
- A reviewer should scrutinize: the event emission parity (both paths emit
  `inventory_changed` once after commit) and that sale/purchase flows were
  not touched.
