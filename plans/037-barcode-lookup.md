# Plan 037: Unify barcode lookup on ProductService.get_product_by_barcode

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- ui/purchase_view.py ui/inventory_view.py ui/sale_view.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The same "find product by barcode" operation has three implementations:
`ui/sale_view.py:759` uses the parameterized service method
`ProductService.get_product_by_barcode` (SQL, honors `active_only`); 
`ui/purchase_view.py:303-306` (`find_product_by_barcode`) loads the ENTIRE
products table via `get_all_products()` and does a linear Python scan on every
barcode read (cashier hot path); `ui/inventory_view.py:290-296`
(`handle_barcode_scan`) scans only the currently filtered in-memory list and
reports "no encontrado en la vista actual" even when the product exists but is
filtered out (a comment at :299 even admits "Maybe it's not in current filtered
list but exists?"). One O(N)-per-scan lookup, one wrong-negative behavior, and
the correct implementation all coexist. This plan converges all three on the
service method.

## Current state

- `services/product_service.py:283` —
  `def get_product_by_barcode(self, barcode: str, active_only: bool = True) -> Product | None`
  — parameterized SQL (`WHERE p.barcode = ? AND (? = 0 OR p.is_active = 1)`),
  LEFT JOINs categories so `product.category_name` is populated.
- `ui/sale_view.py:759` — the correct pattern to follow:
  `product = self.product_service.get_product_by_barcode(barcode)` (verify with
  `grep -n "get_product_by_barcode" ui/sale_view.py`).
- `ui/purchase_view.py:277` — `product = self.find_product_by_barcode(barcode)`.
- `ui/purchase_view.py:303-306` — the O(N) re-implementation:
  ```python
  def find_product_by_barcode(self, barcode: str) -> Any | None:
      """Find a product by its barcode."""
      products = self.product_service.get_all_products()
      return next((p for p in products if p.barcode == barcode), None)
  ```
- `ui/inventory_view.py:290-296` — scans `self.current_inventory` (the
  filtered list set in `load_inventory` at :229) for a dict with matching
  `"barcode"`, then calls `self.edit_inventory(item)`. Not-found path shows
  "no encontrado en la vista actual" (`:309`).
- `ui/inventory_view.py:272-283` — `edit_inventory(item)` takes a dict with
  keys `product_id`, `product_name`, `category_name`, `barcode`, `quantity`
  and passes `item["product_id"]` to `inventory_service.adjust_inventory`.

**Repo conventions**:
- Services own DB access; UI never writes SQL directly.
- Error feedback via `show_error_message` + a red flash on the barcode input
  (sale_view uses `DesignTokens.COLOR_ERROR_BG`; purchase_view hardcodes
  `"#ffebee"` — the hardcode is normalized in plan 052, keep it as-is here).
- Spanish UI strings.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Purchase UI tests | `.venv/bin/python -m pytest tests/test_ui/ -k "purchase or barcode or scan"` | all pass |
| Inventory UI tests | `.venv/bin/python -m pytest tests/test_ui/test_inventory_view.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `ui/purchase_view.py`
- `ui/inventory_view.py`
- `tests/test_ui/` (new tests)

**Out of scope**:
- `ui/sale_view.py` (already correct — used as the pattern reference)
- `services/product_service.py` (the service method is correct; no changes)
- The `#ffebee` color normalization (plan 052)
- `inventory_view.py` category/search filtering logic (only the barcode scan changes)

## Git workflow

- Branch: `advisor/037-barcode-lookup`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: purchase_view uses the service method

In `ui/purchase_view.py`:
- Replace `self.find_product_by_barcode(barcode)` at :277 with
  `self.product_service.get_product_by_barcode(barcode)`.
- Delete `find_product_by_barcode` (:303-306).

**Verify**: `grep -n "find_product_by_barcode" ui/purchase_view.py` → no matches.
`grep -rn "find_product_by_barcode" ui/ tests/` → no matches anywhere.

### Step 2: inventory_view uses the service method

In `ui/inventory_view.py`, rewrite `handle_barcode_scan` (:285-312) to:
1. Look up `product = self.product_service.get_product_by_barcode(barcode)`.
2. If found, build the item dict `edit_inventory` expects and call it:
   ```python
   inventory = self.inventory_service.get_inventory(product.id)
   item = {
       "product_id": product.id,
       "product_name": product.name,
       "category_name": product.category_name or "Sin Categoría",
       "barcode": product.barcode,
       "quantity": float(inventory.quantity) if inventory else 0.0,
   }
   self.edit_inventory(item)
   ```
3. If not found, show the red flash + error message. Change the message from
   "no encontrado en la vista actual" to something accurate, e.g.
   "Producto con código {barcode} no encontrado". Remove the speculative
   "Maybe it's not in current filtered list but exists?" comment.
4. Clear the input in a `finally:` block (preserve current clear-on-all-paths behavior).

Note: `Product.id` is typed `int | None`; `get_product_by_barcode` returns
products from the DB so `id` is never None in practice — guard with
`if product.id is None: raise ValidationException(...)` if pyright complains
(pyright is strict; match its expectations).

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_inventory_view.py` → all pass.
`grep -n "current_inventory" ui/inventory_view.py` → only the assignment in
`load_inventory` (:229) and any other genuinely separate uses remain (not the scan).

### Step 3: Add regression tests

Add tests under `tests/test_ui/` covering:
- **purchase_view**: scanning a barcode calls `product_service.get_product_by_barcode`
  (mock the service) and, on hit, opens the item dialog with that product.
- **inventory_view**: scanning a barcode whose product exists calls
  `edit_inventory` even when the product is NOT in the currently filtered
  list (regression for the wrong-negative bug).

Use the existing qtbot patterns in `tests/test_ui/` (CI runs UI tests under
xvfb; tests must request the `qtbot`/`qapp` fixture — see `tests/conftest.py`).

**Verify**: the new tests fail on the old code path (for inventory: run with
the filter excluding the product) and pass on the new code.

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- New qtbot tests for the two views (Step 3). Pattern: existing
  `tests/test_ui/test_inventory_view.py` and `tests/test_ui/test_sale_view_ux.py`.
- The inventory regression test must prove a product hidden by the current
  filter is still found and opened for editing.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "find_product_by_barcode" ui/ tests/` returns no matches
- [ ] `grep -n "no encontrado en la vista actual" ui/` returns no matches
- [ ] `ui/purchase_view.py` and `ui/inventory_view.py` both call
      `product_service.get_product_by_barcode` (grep confirms)
- [ ] New regression tests exist and pass
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- `get_product_by_barcode` is NOT available on the `product_service` instance
  in either view (check the service instantiation and the method signature).
- A test asserts the old "no encontrado en la vista actual" message.
- `Product` objects lack a `category_name` attribute (the service JOIN populates
  it — verify with the sale_view usage before assuming).

## Maintenance notes

- The single lookup path is now `ProductService.get_product_by_barcode`. Any
  future view that scans barcodes should reuse it — do not re-scan in-memory lists.
- Plan 052 later consolidates the scan/search/selection dialog scaffolding and
  normalizes the `#ffebee` hardcode to `DesignTokens.COLOR_ERROR_BG`; this
  plan intentionally leaves that color alone to keep the two plans independent.
- Reviewer should sanity-check that scanning a barcode in purchase_view still
  plays the success sound and opens `PurchaseItemDialog` (behavior preserved).