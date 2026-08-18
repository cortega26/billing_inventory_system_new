# Plan 051: Consolidate table action-cell, WaitCursor, and confirm-dialog scaffolding

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- utils/ui/table_items.py ui/sale_view_tables.py ui/purchase_view.py ui/product_view.py ui/customer_view.py ui/inventory_view.py ui/main_window.py ui/category_management_dialog.py ui/sale_view.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

Seven views re-implement the same "cell with centered buttons" widget
(`QWidget` + `QHBoxLayout` + `setContentsMargins(0,0,0,0)` + `setSpacing` +
`AlignCenter` + `QPushButton` + `setFixedWidth(80)` + `setStyleSheet("padding:
2px 8px;")` + `setRowHeight(36)`), and they have ALREADY drifted (product/customer
use `setFixedHeight(24)`, sale/purchase don't). Eleven sites repeat the
`QApplication.setOverrideCursor(WaitCursor)` / `restoreOverrideCursor` pair.
`utils/helpers.py:152` defines `confirm_action` but only 1 of 7 confirmation
sites uses it — the other 6 inline `QMessageBox.question` (with inconsistent
Spanish/English titles). This plan extracts the shared helpers and routes the
inline confirmations through the existing one.

## Current state

- Actions-cell scaffold sites (grep `setFixedWidth(80)` = 9, `padding: 2px 8px` = 9):
  - `ui/sale_view_tables.py:109-120` (`_build_remove_action_widget`),
    `:123-150` (`_build_sale_history_actions_widget`)
  - `ui/purchase_view.py:334-346`, `:415-437`
  - `ui/product_view.py:360-387` (uses `setFixedHeight(24)`)
  - `ui/customer_view.py:313-339` (uses `setFixedHeight(24)`)
  - `ui/inventory_view.py:252-266`
- WaitCursor pairs (grep `setOverrideCursor`): `ui/product_view.py:291,311,497,528,548,588`,
  `ui/customer_view.py:215`, `ui/sale_view.py:1036`, `ui/purchase_view.py:445`,
  `ui/inventory_view.py:193`, `ui/analytics_view.py:152`.
- Confirmation sites: `ui/helpers.py:152` `confirm_action(parent, title, message)`
  is used ONLY at `ui/sale_view.py:1155`. Inline `QMessageBox.question`:
  `ui/purchase_view.py:588`, `ui/product_view.py:488`, `ui/customer_view.py:441,551`,
  `ui/main_window.py:287`, `ui/category_management_dialog.py:163`.
- `utils/ui/table_items.py` — home of the table-item classes (numeric/price/date/
  percentage/checkbox) and already imports Qt + QTableWidgetItem — the natural
  home for a `build_actions_cell` helper.

**Repo conventions**:
- UI helpers live under `utils/ui/` or `utils/helpers.py`.
- Spanish user-facing strings; button labels are Spanish ("Editar", "Eliminar",
  "Restaurar").
- New UI helpers must be covered by a qtbot test (CI runs under xvfb).

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Affected UI tests | `.venv/bin/python -m pytest tests/test_ui/` | all pass (xvfb) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `utils/ui/table_items.py` (new helper)
- `utils/helpers.py` (WaitCursor context manager)
- `ui/sale_view_tables.py`, `ui/purchase_view.py`, `ui/product_view.py`,
  `ui/customer_view.py`, `ui/inventory_view.py`, `ui/analytics_view.py`,
  `ui/main_window.py`, `ui/category_management_dialog.py`, `ui/sale_view.py`
- `tests/test_ui/` (new tests)

**Out of scope**:
- The per-view table-fill logic (only the cell/button widget + cursor + confirm)
- The `show_error_message` vs `show_error_dialog` duplication (separate concern;
  they have different pytest-suppression semantics)
- Any button styling change beyond normalizing the 2 drifted variants (the
  extraction may keep per-call options for height)

## Git workflow

- Branch: `advisor/051-table-scaffold`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add build_actions_cell + wait_cursor helpers

In `utils/ui/table_items.py`, add:

```python
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

def build_actions_cell(*buttons: QPushButton, spacing: int = 6) -> QWidget:
    """Wrap buttons in a centered actions cell for a table row."""
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    for button in buttons:
        layout.addWidget(button)
    return widget

def action_button(label: str, on_click, *, width: int = 80, height: int | None = None) -> QPushButton:
    """Standard table action button (Spanish label, padded)."""
    button = QPushButton(label)
    button.setFixedWidth(width)
    if height is not None:
        button.setFixedHeight(height)
    button.setStyleSheet("padding: 2px 8px;")
    button.clicked.connect(on_click)
    return button
```

In `utils/helpers.py`, add a context manager:

```python
from contextlib import contextmanager

@contextmanager
def wait_cursor():
    """Show the wait cursor for the duration of the block."""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()
```

(`QApplication`/`Qt` imports must be added to helpers.py if absent — check the
file's imports first.)

**Verify**: `.venv/bin/python -c "from utils.ui.table_items import build_actions_cell, action_button; from utils.helpers import wait_cursor"` → exit 0.

### Step 2: Convert the actions-cell sites

Replace each of the 7 inline scaffolds with `build_actions_cell` +
`action_button`, normalizing the drifted variants:
- `ui/sale_view_tables.py` — `_build_remove_action_widget` uses
  `action_button("Eliminar", lambda: remove_handler(row))`; the history widget
  builds 4 emoji buttons (width 36, `padding: 2px 4px`) — pass those as
  positional buttons to `build_actions_cell(..., spacing=4)`.
- `ui/purchase_view.py`, `ui/product_view.py` (height 24), `ui/customer_view.py`
  (height 24), `ui/inventory_view.py` — use the helpers, preserving each view's
  button labels and the height where it existed. The extraction NORMALIZES the
  height difference (pick 24 for all, the majority/style-most-consistent) —
  confirm this is the intended normalization; if a view visually depends on
  un-fixed height, pass `height=None` for it and note why.

**Verify**: `grep -c "setContentsMargins(0, 0, 0, 0)" ui/*.py` drops to the
helper file only; `.venv/bin/python -m pytest tests/test_ui/` → pass.

### Step 3: Convert the WaitCursor sites

Replace each `QApplication.setOverrideCursor(...) ... finally:
restoreOverrideCursor()` with `with wait_cursor():` wrapping the body. Keep the
`try/finally` where there is other cleanup in the `finally` block (e.g.
`ui/product_view.py:302-303` restores cursor AND nothing else — inspect each;
if the finally does more, keep the manual restore and just reuse the
context manager inside, or keep the manual form — the goal is removing the 11
inline pairs where they are a pure cursor pair).

**Verify**: `grep -c "setOverrideCursor" ui/*.py` → only the helper's one
occurrence (and any site where a finally does more than restore — document those).

### Step 4: Route inline confirmations through confirm_action

Replace the 6 inline `QMessageBox.question` sites with `confirm_action(self,
title, message)` (or `confirm_action(None, ...)` in the dialog), preserving the
existing Spanish titles/messages exactly:
- `ui/purchase_view.py:588`, `ui/product_view.py:488`,
  `ui/customer_view.py:441,551`, `ui/main_window.py:287`,
  `ui/category_management_dialog.py:163`.
Delete the now-unused `QMessageBox` imports where ruff flags them.

**Verify**: `grep -rn "QMessageBox.question" ui/` → no matches.
`.venv/bin/python -m pytest tests/test_ui/` → pass.

### Step 5: Add a helper test + full verification

Add a qtbot test in `tests/test_ui/` asserting `build_actions_cell` returns a
widget whose layout has the expected alignment/margins and that `action_button`
creates a clickable button emitting its handler (pattern: existing
`tests/test_ui/test_sale_view_tables.py`).

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- New qtbot test for `build_actions_cell`/`action_button` (Step 5).
- Existing UI tests cover the converted sites; run the full UI suite after each
  step.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "QMessageBox.question" ui/` returns no matches
- [ ] `grep -c "setContentsMargins(0, 0, 0, 0)" ui/sale_view_tables.py ui/purchase_view.py ui/product_view.py ui/customer_view.py ui/inventory_view.py` → 0 (all in the helper)
- [ ] `grep -rn "setOverrideCursor" ui/` → only the helper's `wait_cursor` (plus documented exceptions)
- [ ] New helper test exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- Normalizing the button-height difference (24 vs unset) breaks a UI test
  (report the failing test instead of reverting).
- A `finally:` block in a WaitCursor site does more than restore the cursor —
  keep the manual form there and document it.
- A confirmation dialog's parent/semantics differ between `QMessageBox.question`
  and `confirm_action` in a way that changes behavior (verify `confirm_action`
  defaults to `No` — match the inline sites' default button).

## Maintenance notes

- New table views should use `build_actions_cell`/`action_button` +
  `wait_cursor` + `confirm_action` — they are the consolidated primitives.
- The `show_error_message` vs `show_error_dialog` duplication remains a known
  follow-up (different pytest-suppression semantics make a blind merge risky).
- Reviewer should visually verify one table per view (products, customers,
  inventory, purchases, sales history) for unchanged button layout and that
  deletion confirmations still read in Spanish.