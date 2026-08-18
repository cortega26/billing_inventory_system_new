# Plan 055: Flatten the worst table-refresh nesting (preserve silent row skip)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- ui/product_view.py ui/customer_view.py ui/dashboard_view.py ui/sale_view.py services/inventory_service.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The two table-refresh methods (`product_view.update_product_table` and
`customer_view.populate_customer_table`) nest 4-5 levels deep
(`try > for > try > 40-line row body > except: continue`), making them the
least readable code in the repo. The per-row `except: continue` silently drops
rows — a behavior the maintainer decided to PRESERVE (2026-08-17), but the
nesting can be flattened by extracting the row renderer so the loop reads
cleanly. `dashboard_view.update_backup_status` has a 4-level conditional with a
silent `except: pass` (a textbook early-exit candidate), and
`sale_view.handle_barcode_scan` duplicates its stock-warning block between the
quick-scan and dialog paths.

## Current state

- `ui/product_view.py:305-405` — `update_product_table`: outer `try`, `for row,
  product in enumerate(products)`, inner `try` with a ~40-line body building
  items/buttons, `except Exception: logger.error(...); continue` at :388-390,
  outer `except ... raise UIException` at :399-403, `finally: restoreOverrideCursor`.
- `ui/customer_view.py:236-364` — `populate_customer_table`: same shape with a
  per-row `except: continue` and step-numbered comments ("1) ... 8)").
- `ui/dashboard_view.py:294-341` — `update_backup_status`: nested
  `if last_skipped: if not last_success: ... else: try: ... except Exception: pass`
  (verify exact lines; the `is_at_risk` computation is the early-exit target).
- `ui/sale_view.py:751-819` — `handle_barcode_scan`: the stock-warning block
  (:772-788, sets `scan_warning_label` + status message) is written once for the
  quick-scan path; the dialog path does NOT warn (verify) — the duplication is
  the warning text/format string appearing in both the label and the status
  message. Extract the message builder.
- `services/inventory_service.py:98-132` — `update_quantity`: `if inventory:
  ... else: ...` where the else branch can early-return, avoiding the trailing
  `if emit_events` re-check at :126.

**Behavior to preserve** (maintainer decision 2026-08-17): a row that fails to
render is SKIPPED silently (only a log/warning); the table still fills with the
rows that succeed.

**Repo conventions**: Spanish UI strings; early-exit style; no new runtime
behavior in a refactor.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Affected UI tests | `.venv/bin/python -m pytest tests/test_ui/test_product_view.py tests/test_ui/test_customer_view.py tests/test_ui/test_dashboard_view.py tests/test_ui/test_sale_view_ux.py` | all pass (xvfb) |
| Inventory tests | `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `ui/product_view.py`, `ui/customer_view.py`, `ui/dashboard_view.py`,
  `ui/sale_view.py`, `services/inventory_service.py`

**Out of scope**:
- Changing the row-skip behavior (silent skip stays)
- The table cells/actions extraction (plan 051) — do not duplicate it here
- Any metric/UI text change beyond the stock-warning message builder

## Git workflow

- Branch: `advisor/055-flatten-nesting`
- Commit per logical unit (`refactor: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Extract the row renderers (product + customer tables)

In `ui/product_view.py`, extract the ~40-line row-building body into a private
method `_render_product_row(self, row, product)` that does the `setItem` /
`setCellWidget` / `setRowHeight` calls and RAISES on failure. Rewrite the loop:

```python
for row, product in enumerate(products):
    try:
        self._render_product_row(row, product)
    except Exception as e:
        logger.warning(f"Skipping row {row} (product {product.id}): {str(e)}")
        continue
```

Do the same in `ui/customer_view.py` (`_render_customer_row`). Remove the
step-numbered comments from the loop (they belong inside the helper or are
unneeded after extraction).

**Verify**: the loops are 3 levels deep max; `.venv/bin/python -m pytest tests/test_ui/test_product_view.py tests/test_ui/test_customer_view.py` → pass.

### Step 2: Early-exit update_backup_status

In `ui/dashboard_view.py`, restructure `update_backup_status` to compute the
risk state with early returns (e.g. a helper `_compute_backup_risk()` that
returns early on the first decisive condition) and remove the nested
`except: pass` swallow by handling the parse failure in one place.

**Verify**: `grep -n "except Exception: pass" ui/dashboard_view.py` → no matches.
`.venv/bin/python -m pytest tests/test_ui/test_dashboard_view.py` → pass.

### Step 3: Extract the stock-warning message builder

In `ui/sale_view.py`, add a helper `_build_stock_warning(product_name, current_stock) -> str`
returning the `"⚠️ ¡Advertencia! El producto '{name}' tiene stock bajo. Disponible: {n} unidades"`
string, and use it for BOTH the label (:772-774) and the status message (:785-788).
If the dialog path should also warn, do NOT add new behavior — only dedupe the
string.

**Verify**: `grep -c "tiene stock bajo" ui/sale_view.py` → 1 (the helper)
plus 2 call sites (label + status). `.venv/bin/python -m pytest tests/test_ui/test_sale_view_ux.py` → pass.

### Step 4: Early-return in update_quantity

In `services/inventory_service.py:98-132`, restructure so the non-existent-
inventory branch returns after creating the row, and the existing-inventory
branch runs the emit block without the trailing re-check. Preserve the exact
validation/rounding logic.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_inventory_service.py tests/test_critical_backend_flows.py` → pass.

### Step 5: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- No new tests required (pure restructure; existing UI/service tests cover the
  behavior). If a test asserted the old per-row `logger.error` text, update it
  to the new `logger.warning` text.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -n "except Exception: pass" ui/dashboard_view.py` returns no matches
- [ ] The product/customer table loops are max 3 levels deep (visual inspection;
      `ruff` will flag complexity regressions via `C90` if enabled — it is not
      in the current lint set, so verify by reading)
- [ ] `grep -c "tiene stock bajo" ui/sale_view.py` ≤ 3 (1 helper + 2 call sites)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- Extracting the row renderer changes what a failing row does (it must still be
  skipped with a log line — if a test asserts rows are NOT skipped, report).
- `update_backup_status`'s risk computation has a case where the old code
  produced a result the early-return version doesn't (map all input states
  before restructuring).
- The stock-warning text is asserted by a test that breaks.

## Maintenance notes

- Row renderers are the pattern for future table views: a `_render_<X>_row`
  helper + a thin loop with a per-row skip.
- Plan 051 extracts the cell/button widgets these renderers use; run 051 first
  or coordinate if they overlap (they don't — 051 targets the cell builder,
  this targets the loop structure).