# Plan 052: Extract shared scan/selection scaffolding; normalize error flash

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- ui/sale_view.py ui/purchase_view.py ui/scan_support.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: 037 (barcode lookup already unified on the service method)
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The product-scan/search/selection flow is scaffolded three times — twice in
`ui/sale_view.py` (in `EditSaleDialog` and in `SaleView`) and once in
`ui/purchase_view.py` — and the copies have drifted: the error flash uses
`DesignTokens.COLOR_ERROR_BG` in sale_view but a hardcoded `"#ffebee"` in
purchase_view, the selection dialog's barcode label differs ("(Código:" vs
"(Código de Barras:"), and `handle_barcode_input` (length>14 clears) is
duplicated. This plan extracts the shared scaffolding (`flash_input_error`,
`show_product_selection_dialog`, `on_barcode_length_exceeded`) into
`ui/scan_support.py` and routes both views through it. The full scan-flow
unification (quick-scan branch + stock warning + item-dialog factory
parameterization) is deliberately deferred — it touches cashier behavior and
needs a design review first.

## Current state

- `ui/sale_view.py:745-749` — `handle_barcode_input` (length>14 → clear).
- `ui/purchase_view.py:263-267` — same `handle_barcode_input`.
- `ui/sale_view.py:221-246` — `EditSaleDialog.handle_barcode_scan`:
  service lookup → `SaleItemDialog` → error flash via `DesignTokens.COLOR_ERROR_BG` (:235-240) → `show_error_message`.
- `ui/sale_view.py:751-819` — `SaleView.handle_barcode_scan`: same + sound +
  quick-scan branch + stock warning (:764-792) + `finally: barcode_input.clear()`.
- `ui/sale_view.py:286-311` — `SaleView.show_product_selection_dialog` (label
  "(Código: ...)").
- `ui/purchase_view.py:490-515` — `PurchaseView.show_product_selection_dialog`
  (label "(Código de Barras: ...)").
- `ui/purchase_view.py:290-295` — error flash hardcoded `"#ffebee"`.
- `ui/sale_view.py:248-273` / `ui/purchase_view.py:458-488` — `search_products`
  (call the per-view selection dialog / item dialog).
- `ui/styles.py` — has `DesignTokens.COLOR_ERROR_BG` (used by sale_view).

**Repo conventions**:
- Shared UI widgets/helpers live under `utils/ui/` or a small `ui/` support
  module (the repo already splits `ui/sale_view_support.py`,
  `ui/sale_view_tables.py`).
- Spanish user-facing strings.
- New UI support code needs a qtbot test (CI runs under xvfb).

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Sale/purchase UI tests | `.venv/bin/python -m pytest tests/test_ui/` | all pass (xvfb) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `ui/scan_support.py` (new)
- `ui/sale_view.py`
- `ui/purchase_view.py`
- `tests/test_ui/` (new test)

**Out of scope**:
- The quick-scan branch + stock-warning block in `SaleView.handle_barcode_scan`
  (:764-792) — kept as-is, referenced in maintenance notes (deferred
  unification)
- `search_products` bodies (they call the shared selection dialog; their
  per-view item-dialog calls stay)
- The item dialogs themselves (`SaleItemDialog`, `PurchaseItemDialog`) — their
  shared QFormLayout scaffolding is a separate consolidation (audit finding,
  deferred)
- The `#ffebee` normalization is IN scope (it is part of the flash helper)

## Git workflow

- Branch: `advisor/052-scan-support`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Create ui/scan_support.py

Create `ui/scan_support.py` with:

```python
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from ui.styles import DesignTokens

MAX_BARCODE_LENGTH = 14  # EAN-14 is the longest common barcode

def flash_input_error(widget: QWidget) -> None:
    """Flash a widget's background red to signal a failed scan."""
    widget.setStyleSheet(f"background-color: {DesignTokens.COLOR_ERROR_BG};")
    QTimer.singleShot(1000, lambda: widget.setStyleSheet(""))

def on_barcode_length_exceeded(barcode_input) -> None:
    """Clear over-long barcode input (scanner garbling guard)."""
    if len(barcode_input.text()) > MAX_BARCODE_LENGTH:
        barcode_input.clear()

def show_product_selection_dialog(products, parent: QWidget | None) -> object | None:
    """Show a picker for multiple matching products; return the chosen product."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Seleccionar Producto")
    layout = QVBoxLayout(dialog)

    product_list = QComboBox()
    for product in products:
        display_text = f"{product.name}"
        if getattr(product, "barcode", None):
            display_text += f" (Código: {product.barcode})"
        product_list.addItem(display_text, product)

    layout.addWidget(QLabel("Seleccione un producto:"))
    layout.addWidget(product_list)

    button_box = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return product_list.currentData()
    return None
```

Note: the label text is normalized to "(Código: ...)" (the purchase_view
variant "(Código de Barras: ...)" becomes "(Código: ...)" — a trivial wording
normalization; if a UI test pins the longer text, update it).

**Verify**: `.venv/bin/python -c "import ui.scan_support"` → exit 0.

### Step 2: Route both views through the shared helpers

In `ui/sale_view.py`:
- Replace the two `handle_barcode_input` bodies (:745-749 and the EditSaleDialog
  variant at :221 region — check) with `on_barcode_length_exceeded(self.barcode_input)`.
- Replace the not-found error flash blocks (:235-240 and :804-809) with
  `flash_input_error(self.barcode_input)`.
- Replace `show_product_selection_dialog` bodies (:286-311 and the EditSaleDialog
  variant if it exists) with a call to the shared function.
- Remove the now-inline `from ui.styles import DesignTokens` imports in those
  methods if they become unused (keep the top-level import if present).

In `ui/purchase_view.py`:
- Replace `handle_barcode_input` (:263-267) with `on_barcode_length_exceeded(self.barcode_input)`.
- Replace the `"#ffebee"` flash (:292-293) with `flash_input_error(self.barcode_input)`.
- Replace `show_product_selection_dialog` (:490-515) with the shared call.

**Verify**: `grep -n "#ffebee" ui/` → no matches. `grep -rn "flash_input_error\|on_barcode_length_exceeded\|show_product_selection_dialog" ui/sale_view.py ui/purchase_view.py` → used, and their old bodies are gone.

### Step 3: Add a helper test

Add a qtbot test in `tests/test_ui/test_scan_support.py` (or extend an existing
UI test file) covering: `on_barcode_length_exceeded` clears an over-long input,
`flash_input_error` sets a stylesheet then resets it (use `QTest.qWait` for the
timer), and `show_product_selection_dialog` returns the selected product on Ok.
Pattern: existing `tests/test_ui/test_sale_view_ux.py`.

**Verify**: `.venv/bin/python -m pytest tests/test_ui/` → all pass.

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- New qtbot test file for `ui/scan_support.py` (Step 3).
- Existing UI tests cover the views' scan/search flows; run the full UI suite.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "#ffebee" ui/` returns no matches
- [ ] `grep -rn "def show_product_selection_dialog\|def handle_barcode_input" ui/sale_view.py ui/purchase_view.py` returns no matches (only `ui/scan_support.py` has them)
- [ ] `grep -c "from ui.styles import DesignTokens" ui/sale_view.py ui/purchase_view.py` → top-level imports only (no in-body imports)
- [ ] New scan-support test exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A UI test pins the "(Código de Barras:" label text and the normalization is
  disputed (report; do not silently keep two label formats in the shared fn).
- The EditSaleDialog variant of `show_product_selection_dialog`/scan uses
  different parent/semantics than the SaleView variant (read both before
  replacing; if they differ materially, keep them separate and report).
- Removing the in-body `DesignTokens` import breaks a method that still uses it.

## Maintenance notes

- The deeper scan-flow unification (quick-scan branch, stock warning, item
  dialog factory) is deferred: it changes cashier-facing behavior and needs a
  design review. The shared helpers make that future unification mechanical.
- The item dialogs' shared QFormLayout scaffolding is a separate deferred
  consolidation (audit finding).
- New views with a barcode scanner should reuse `ui/scan_support.py`.
- Reviewer should verify scan error feedback looks identical in sale, purchase,
  and inventory views (same red flash + Spanish error).