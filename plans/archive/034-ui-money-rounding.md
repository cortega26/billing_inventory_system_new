# Plan 034: Route all UI money totals through FinancialCalculator's ROUND_HALF_UP

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- ui/sale_view_tables.py ui/purchase_view.py ui/sale_view.py utils/math/financial_calculator.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The UI computes item totals with Python's built-in `round()` (round-half-even:
`round(1501.5)` → `1502`) while the services persist totals via
`FinancialCalculator.calculate_item_total` (round-half-up: `1501.5` → `1502`
only if the half lands such that banker's and half-up differ — they differ
whenever the exact half value rounds to an even integer under banker's, e.g.
`round(750.5)` → `750` but ROUND_HALF_UP → `751`). For quantities with a `.5`
in the decimals (e.g. quantity `1.5` × price `501` = `751.5`), the on-screen
total/label can disagree with the total stored in the sales/purchases tables by
1 CLP. Two implementations of "item total" with different rounding rules is the
exact kind of silent divergence that produces "UI shows one number, record
stores another" bugs.

## Current state

- `ui/sale_view_tables.py:33` — quantity display rounding:
  `quantity_item = NumericTableWidgetItem(round(item["quantity"], 3))` (this is
  display-only rounding of a quantity, NOT money — leave it).
- `ui/sale_view_tables.py:40` — item total (money, WRONG rounding):
  `total = int(round(item["quantity"] * item["sell_price"]))`
- `ui/sale_view_tables.py:51-53` — sale-total label (money, WRONG rounding):
  `total_amount = sum(int(round(item["quantity"] * item["sell_price"])) for item in sale_items)`
- `ui/purchase_view.py:105` — purchase-item total in dialog (money, WRONG):
  `total = round(quantity * price)`
- `ui/purchase_view.py:327` — purchase-item total in table (money, WRONG):
  `item_total = round(item["quantity"] * item["cost_price"])`
- `utils/math/financial_calculator.py:24-34` — the authoritative total:
  `calculate_item_total` quantizes with `ROUND_HALF_UP`.
- `services/sale_service.py:81-86` and `services/purchase_service.py:39-44` —
  services already sum totals through `FinancialCalculator.calculate_item_total`.
- `ui/sale_view.py:913-916` — re-implements item profit with raw `round()` in
  `adjust_selected_quantity` (verify exact lines with grep before editing; the
  file is 1347 lines and may have shifted).

**Repo conventions** (match these):
- Money is CLP integer-only; rounding policy is ROUND_HALF_UP, owned by
  `FinancialCalculator` (`utils/math/financial_calculator.py`).
- UI imports `FinancialCalculator` already in `sale_view.py` and
  `purchase_view.py` — reuse the existing import, do not add new helpers.
- Error handling: do not add new try/except in these functions; they are pure
  rendering helpers.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Targeted tests | `.venv/bin/python -m pytest tests/test_ui/test_sale_view_tables.py tests/test_ui/test_sale_view_helpers.py` | all pass |
| Purchase UI tests | `.venv/bin/python -m pytest tests/test_ui/test_purchase_view.py 2>/dev/null; ls tests/test_ui/ | grep -i purchase` | see note: check whether purchase UI tests exist |
| Full suite | `.venv/bin/python -m pytest` | all pass (395+ tests) |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `ui/sale_view_tables.py`
- `ui/purchase_view.py`
- `ui/sale_view.py` (only the profit recompute line)
- `tests/test_ui/` (new/updated tests)

**Out of scope**:
- `utils/math/financial_calculator.py` (its rounding policy is correct; do not change it)
- Service-layer total computation (already correct)
- Any change to quantity display rounding (`round(item["quantity"], 3)` stays)

## Git workflow

- Branch: `advisor/034-ui-money-rounding`
- Commit per logical unit; message style matches repo (`refactor: ...`,
  `tests: ...` — see `git log --oneline`).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Route the sale-view totals through FinancialCalculator

In `ui/sale_view_tables.py`:
- Replace line 40 with:
  `total = FinancialCalculator.calculate_item_total(item["quantity"], item["sell_price"])`
- Replace lines 51-53 with:
  `total_amount = sum(FinancialCalculator.calculate_item_total(item["quantity"], item["sell_price"]) for item in sale_items)`
- Add the import at the top (follow existing import ordering):
  `from utils.math.financial_calculator import FinancialCalculator`

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_sale_view_tables.py` → all pass. `grep -rn "int(round(item\[.quantity" ui/sale_view_tables.py` → no matches.

### Step 2: Route the purchase-view totals through FinancialCalculator

In `ui/purchase_view.py`:
- Replace line 105 (`total = round(quantity * price)`) with
  `total = FinancialCalculator.calculate_item_total(quantity, price)`
- Replace line 327 (`item_total = round(item["quantity"] * item["cost_price"])`) with
  `item_total = FinancialCalculator.calculate_item_total(item["quantity"], item["cost_price"])`
- Add the import if not already present.

**Verify**: `grep -rn "round(item\[.quantity.*item\[.cost_price\|round(quantity \* price)" ui/purchase_view.py` → no matches.

### Step 3: Fix the profit recompute in sale_view.py

Find the profit recompute (agent-reported near line 913-916; locate with:
`grep -n "adjust_selected_quantity\|round(" ui/sale_view.py | head -30`). Replace
the raw `round(qty * (sell - cost))` with
`FinancialCalculator.calculate_item_profit(qty, sell_price, cost_price)`
(follow the signature at `financial_calculator.py:37`).

**Verify**: `grep -n "adjust_selected_quantity" ui/sale_view.py` shows the method; the raw
profit `round(` is gone from that method body.

### Step 4: Add regression tests

Add a test file (or extend an existing one) under `tests/test_ui/` covering the
rounding divergence. Use `.venv/bin/python -m pytest tests/test_ui/test_sale_view_tables.py`
to see the existing test structure and mirror it. Tests must cover:
- An item where `quantity * price` lands on `.5` and banker's would round DOWN
  while ROUND_HALF_UP rounds UP (e.g. quantity `1.5`, price `501` → `751.5`:
  assert total is `752`). Verify this exact pair in Python first with
  `.venv/bin/python -c "print(round(1.5*501))"` (→ 752) and
  `.venv/bin/python -c "from utils.math.financial_calculator import FinancialCalculator as F; print(F.calculate_item_total(1.5, 501))"` (→ 752) —
  if both agree for this pair, pick a pair where they disagree (e.g. `0.5 * 1501 = 750.5`:
  `round(750.5)` → 750, ROUND_HALF_UP → 751). Assert the ROUND_HALF_UP result.

**Verify**: the new test fails on the OLD code (run it against `git stash` if
needed to confirm) and passes on the new code. Then the full targeted suite passes.

### Step 5: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- New tests under `tests/test_ui/` asserting `calculate_item_total` semantics
  for the divergent half case (see Step 4). Pattern: existing
  `tests/test_ui/test_sale_view_tables.py`.
- If a test anywhere pins an old `round()` total value, update the expected
  value to the ROUND_HALF_UP result and note it in the commit message.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0 (full suite)
- [ ] No `int(round(` / `round(` money-total expressions remain in
  `ui/sale_view_tables.py` or `ui/purchase_view.py` (grep clean; quantity
  display rounding `round(x, 3)` may remain)
- [ ] New regression test for the half-cent divergence exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the cited locations doesn't match the excerpts (drift).
- A test that asserted an old `round()` total is failing in a way that
  suggests a DIFFERENT rounding intent than ROUND_HALF_UP (report the
  discrepancy instead of silently changing the expected value).
- The `FinancialCalculator` import is missing and adding it creates a circular
  import (report — do not inline the rounding).

## Maintenance notes

- Any new UI money computation must go through `FinancialCalculator`; if a
  future plan touches `validate_money_multiplication`
  (`utils/validation/validators.py:178`) which still uses `round()`, align it
  with ROUND_HALF_UP too and add a test.
- Reviewer should scrutinize: the two `.5`-divergence tests actually assert
  values where banker's and half-up DIFFER (not just any half value).