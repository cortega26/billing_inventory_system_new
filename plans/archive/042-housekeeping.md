# Plan 042: Housekeeping — dead branches, in-loop imports, stale comments

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- ui/sale_view.py ui/dashboard_view.py ui/inventory_view.py ui/main_window.py ui/analytics_view.py services/receipt_service.py services/purchase_query_service.py services/customer_service.py services/sale_service.py main.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

A set of small readability/cleanliness issues that mislead readers or run
imports on hot paths: imports executed inside method bodies and even inside
per-row loops, dead branches on aggregate queries that always return a row,
comments referencing APIs that don't exist or hedges like "old approach" that
signal unresolved decisions, and a shipped menu item that displays placeholder
text. None are bugs; together they are the noise floor that makes the codebase
harder to read than it needs to be.

## Current state

All verified at commit `d560e43`:

1. **In-body / in-loop imports**
   - `ui/sale_view.py:235` and `ui/sale_view.py:804` — `from ui.styles import DesignTokens`
     inside method bodies, though the module already imports it at top level (:51).
   - `ui/dashboard_view.py:359-361` — `from PySide6.QtGui import QColor` and
     `from ui.styles import DesignTokens` inside the per-row loop of
     `update_low_stock`.
   - `ui/inventory_view.py:301` — `from ui.styles import DesignTokens` inside
     `handle_barcode_scan`.
2. **Dead branches on aggregate queries** (SQLite `COUNT`/`SUM`/`COUNT(DISTINCT)`
   always return exactly one row, so the "no row" branch is unreachable):
   - `services/purchase_query_service.py:214-224` — `if not row:` duplicate dict literal.
   - `services/customer_service.py:494-501` — `if result: ... else: return 0, 0`.
   - `services/sale_service.py:623-629` — `if result: ... return {...}`.
3. **Stale/misleading comments**
   - `ui/inventory_view.py:196-198` — "Inventory service might need
     get_inventory_by_category or we filter locally. Assuming get_inventory_status
     returns all and we filter." — `get_inventory_status` does not exist (the
     method is `get_all_inventory`).
   - `ui/analytics_view.py:505` — `# SINGLE-COLUMN BARS (old approach)` (still
     the live path) and `:555` — `# or just max_val` (unresolved axis decision).
   - `services/receipt_service.py:63` — "item.total_price() is a method on SaleItem usually".
   - `ui/sale_view.py:534` — "For now, let's keep it simple, potentially adding
     a generic class if needed."
4. **Shipped placeholder UX** — `ui/main_window.py:476-480` —
   `show_user_guide` shows `"El contenido de la guía de usuario va aquí."` with
   a `# TODO: Implement actual user guide content` comment. No tests reference
   it (grep-verified); the menu entry is at `:169-171`.
5. **Commented-out block** — `main.py:176-179` — dead `# @staticmethod / # def run():` block.

**Repo conventions**:
- Imports at top of module (ruff `I` rules enforce this).
- Spanish user-facing strings.
- No unreferenced placeholder UI.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Affected UI tests | `.venv/bin/python -m pytest tests/test_ui/` | all pass (xvfb) |
| Affected service tests | `.venv/bin/python -m pytest tests/test_services/test_purchase_query_service.py tests/test_services/test_customer_service.py tests/test_services/test_sale_service.py tests/test_services/test_receipt_service.py` | all pass |
| Startup tests | `.venv/bin/python -m pytest tests/test_startup_guard.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**: the files listed in "Current state" (each item maps to one file).
**Out of scope**: any behavioral change beyond the listed cleanups; the
analytics view's single-bar rendering logic; the dashboard's axis-scaling math
(`max_val * 1.1` stays).

## Git workflow

- Branch: `advisor/042-housekeeping`
- Commit per logical unit (`style: ...`, `refactor: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Hoist or delete in-body imports

- `ui/sale_view.py` — delete the two `from ui.styles import DesignTokens` inside
  method bodies (:235, :804); the top-level import at :51 already covers them.
- `ui/dashboard_view.py` — move `from PySide6.QtGui import QColor` to the
  module top (merge with existing QtGui imports); delete the in-loop
  `from ui.styles import DesignTokens` and add `DesignTokens` to the existing
  top-level `ui.styles` import (check current imports; add if missing).
- `ui/inventory_view.py` — hoist `from ui.styles import DesignTokens` to the
  module top.

**Verify**: `grep -n "from ui.styles import DesignTokens\|from PySide6.QtGui import QColor" ui/sale_view.py ui/dashboard_view.py ui/inventory_view.py`
→ matches only at top-level import lines. `.venv/bin/python -m pytest tests/test_ui/` → pass.

### Step 2: Collapse the dead aggregate branches

- `services/purchase_query_service.py:214-224` — build the dict once:
  `row = row or {}` then `return {"total_purchases": row.get("total_purchases", 0), "total_amount": row.get("total_amount", 0), "suppliers": PurchaseQueryService.get_suppliers()}`.
- `services/customer_service.py:494-501` — early-return style:
  `if result is None: logger.warning(...); return 0, 0` then
  `logger.info(...); return result["total_purchases"], result["total_amount"]`.
- `services/sale_service.py:623-629` — `if not result: return {zeros}` then
  build/return the populated dict once.

**Verify**: targeted service tests pass. `grep -n "if not row:\|if result:"` on
the three files shows the new structure.

### Step 3: Fix/remove stale comments

- `ui/inventory_view.py:196-198` — replace the two comment lines with one
  accurate comment: `# Filter the full inventory list locally by category/barcode/search.`
- `ui/analytics_view.py:505` — change `# SINGLE-COLUMN BARS (old approach)` to
  `# Single-series bar chart (one value per category).`
- `ui/analytics_view.py:555` — delete the `# or just max_val` hedge.
- `services/receipt_service.py:63` — delete the "usually" comment (the
  `hasattr(item, "total_price")` check below it already handles both cases).
- `ui/sale_view.py:534` — delete the "keep it simple / maybe generic class" comment.

**Verify**: `grep -rn "get_inventory_status\|old approach\|or just max_val\|potentially adding a generic class\|usually" ui/analytics_view.py ui/inventory_view.py services/receipt_service.py ui/sale_view.py` → no matches.

### Step 4: Remove the placeholder user-guide menu item

In `ui/main_window.py`:
- Remove the menu action at :169-171 (the `"&Guía de Usuario"` entry and its
  trigger).
- Remove the `show_user_guide` method (:476-480).

**Verify**: `grep -rn "show_user_guide\|Guía de Usuario" ui/ tests/` → no matches.
`.venv/bin/python -m pytest tests/test_ui/test_main_window_helpers.py` → pass.

### Step 5: Remove the commented-out block in main.py

Delete `main.py:176-179` (the commented-out `run()` stub).

**Verify**: `grep -n "def run" main.py` → no matches. `.venv/bin/python -m pytest tests/test_startup_guard.py tests/test_smoke.py` → pass.

### Step 6: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- No new behavior tests (cleanup only). Run the affected suites listed above.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "show_user_guide\|Guía de Usuario\|get_inventory_status\|old approach\|or just max_val\|potentially adding a generic class" ui/ services/ main.py` returns no matches
- [ ] In-body `from ui.styles import DesignTokens` / in-loop `QColor` imports are gone (top-level only)
- [ ] `grep -n "TABLE_TOTAL_QUERIES\|def run" main.py` returns no matches
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A UI test asserts the "Guía de Usuario" menu entry exists (none found at plan
  time — verify with grep before deleting).
- The analytics_view `if not row:` branch is reachable for some metric
  (verify the metric query — if any metric can return zero rows for a valid
  input, keep the branch and report instead).
- Removing the `# or just max_val` comment is blocked by an unresolved axis bug
  (report).

## Maintenance notes

- `get_all_inventory` is the single inventory-list source (no
  `get_inventory_status`/`get_inventory_by_category` exists) — future filters
  should extend `load_inventory`'s local filtering.
- The user-guide menu item is gone; if a real guide is built later, add the
  action back with actual content.
- The dashboard/analytics chart rendering is consolidated in plan 054-adjacent
  work; keep the corrected comments consistent with that work.