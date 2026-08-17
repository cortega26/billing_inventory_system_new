# Plan 056: Shared line-item validation; unify per-item INSERT loops

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/sale_service.py services/purchase_service.py utils/validation/item_validators.py tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S-M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The per-item validation in `sale_service` and `purchase_service` is structurally
identical but has DRIFTED: sale allows quantity `min 0.001` with NO upper bound
and price `min 1` with NO cap (no profit cap either), purchase caps quantity at
`9999999.999` and price at `MAX_PRICE_CLP` (with a "Prevent DOS attacks"
comment). The two copies enforce the "same" rule differently with different
error messages, and a policy question (the sale price cap) is undocumented.
Separately, item INSERTs happen three ways: `executemany` in
`create_sale` (`sale_service.py:105-115`) vs per-row loops in
`_insert_sale_items` (`sale_service.py:526-543`) and `_insert_purchase_items`
(`purchase_service.py:248-259`). This plan extracts a parameterized
`validate_line_item`, documents the intentional divergences, and unifies the
INSERT loops on `executemany` — all behavior-preserving (maintainer decision
2026-08-17: keep current limits, do not add a sale price cap).

## Current state

- `services/sale_service.py:490-522` — `_validate_sale_items`: quantity
  `validate_float(..., min_value=0.001)` + 3-decimal check; price
  `validate_integer(..., min_value=1)` + int check; computes profit server-side
  and verifies the product exists.
- `services/purchase_service.py:206-237` — `_validate_purchase_items` +
  `_validate_purchase_item`: quantity `0 < q ≤ 9999999.999` + 3-decimal check;
  price `0 ≤ p ≤ MAX_PRICE_CLP`; no profit computation, no product-exists check
  (the missing product check is a separate known backlog item — NOT in scope).
- INSERT sites:
  - `sale_service.py:101-115` — `create_sale` uses `DatabaseManager.executemany`.
  - `sale_service.py:524-543` — `_insert_sale_items` per-row loop
    (`INSERT INTO sale_items (sale_id, product_id, quantity, price, profit)`).
  - `purchase_service.py:246-259` — `_insert_purchase_items` per-row loop
    (`INSERT INTO purchase_items (purchase_id, product_id, quantity, price)`).

**Repo conventions**:
- `utils/validation/` owns reusable validation primitives (AGENTS.md).
- `DatabaseManager.executemany` is the batched-insert primitive (used in
  `create_sale`); per-row loops are the drift to remove.
- Tests: `tests/test_services/test_sale_service.py` and
  `tests/test_services/test_purchase_service.py` pin item-validation behavior.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Sale/purchase tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py tests/test_critical_backend_flows.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `utils/validation/item_validators.py` (new)
- `services/sale_service.py`
- `services/purchase_service.py`
- `tests/test_validation/` (new tests)

**Out of scope**:
- Adding a sale price/quantity cap (decision deferred to the maintainer)
- Adding a product-exists check to purchase validation (separate backlog item)
- `models/sale.py` / `models/purchase.py` model-side validation (plan 043)

## Git workflow

- Branch: `advisor/056-item-validation`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Create the shared validator

Create `utils/validation/item_validators.py`:

```python
from typing import Any

from utils.exceptions import ValidationException
from utils.validation.validators import validate_float, validate_integer
from models.enums import MAX_PRICE_CLP, QUANTITY_PRECISION  # values only


def validate_line_item(
    item: dict[str, Any],
    *,
    quantity_min: float,
    quantity_max: float | None,
    price_min: int,
    price_max: int | None,
    price_key: str,
    max_items: int,
    entity_label: str,
) -> None:
    """Validate one sale/purchase line item.

    Intentional per-domain limits (do NOT unify without a product decision):
    - Sales: quantity_min=0.001, no quantity_max, price_min=1, no price_max
      (discounted sales may exceed the 1_000_000 unit-price cap).
    - Purchases: quantity_max=9999999.999, price_max=MAX_PRICE_CLP.
    """
    try:
        product_id = int(item.get("product_id", 0))
        if product_id <= 0:
            raise ValidationException(f"Invalid product ID: {product_id}")

        quantity = validate_float(
            item.get("quantity"), min_value=quantity_min, max_value=quantity_max
        )
        if round(quantity, QUANTITY_PRECISION) != quantity:
            raise ValidationException(
                f"Quantity cannot have more than {QUANTITY_PRECISION} decimal places"
            )

        price = validate_integer(
            item.get(price_key), min_value=price_min, max_value=price_max
        )
        item[price_key] = price
        item["quantity"] = quantity
    except (ValueError, TypeError) as e:
        raise ValidationException(f"Invalid item data: {str(e)}") from e
```

(Adjust the signature to also take the items-list guard
`validate_item_count(items, max_items, entity_label)` — add that small helper
to the same module and use it in both services for the "must have at least one
item" / "too many items" checks.)

**Verify**: `.venv/bin/python -c "import utils.validation.item_validators"` → exit 0.

### Step 2: Route both services through it

In `services/sale_service.py`, replace the body of `_validate_sale_items`
(:490-522) with a call to `validate_line_item` using sale limits
(`quantity_min=0.001`, `quantity_max=None`, `price_min=1`, `price_max=None`,
`price_key="sell_price"`) and keep the per-item profit computation + product
existence check AFTER the shared validation (those are sale-specific):
for each item, after `validate_line_item`, look up the product and set
`item["profit"] = FinancialCalculator.calculate_item_profit(...)` as today.

In `services/purchase_service.py`, replace `_validate_purchase_item` (:217-237)
with `validate_line_item` using purchase limits
(`quantity_min=0.001` [the old code used `quantity <= 0` → min effectively 0.001;
use `quantity_min=0.001` to preserve the >0 behavior], `quantity_max=9999999.999`,
`price_min=0`, `price_max=MAX_PRICE_CLP`, `price_key="cost_price"`).

Add a docstring note in each service explaining the intentional divergence (see
the validator's docstring; reference it).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py` → pass (existing tests pin the limits).

### Step 3: Unify the INSERT loops on executemany

- `services/sale_service.py:524-543` — rewrite `_insert_sale_items` to build a
  params list and call `DatabaseManager.executemany` (mirroring `create_sale`'s
  pattern at :101-115). Keep the `round(float(item["quantity"]), QUANTITY_PRECISION)`
  normalization.
- `services/purchase_service.py:246-259` — rewrite `_insert_purchase_items` the
  same way.

**Verify**: `grep -c "INSERT INTO sale_items" services/sale_service.py` → 1 (the
executemany in `create_sale`); the `_insert_sale_items`/`_insert_purchase_items`
bodies contain no `for item in items:` loop. `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py tests/test_critical_backend_flows.py` → pass.

### Step 4: Add validator tests

Add tests in `tests/test_validation/test_item_validators.py` covering:
- A sale-limit item (high price, e.g. 2_000_000) is ACCEPTED by
  `validate_line_item(..., price_max=None)`.
- A purchase-limit item with price > `MAX_PRICE_CLP` is REJECTED.
- A quantity with >3 decimals is rejected (both limit sets).
- `validate_item_count` rejects an empty list and an over-long list.

**Verify**: `.venv/bin/python -m pytest tests/test_validation/` → pass.

### Step 5: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- New `tests/test_validation/test_item_validators.py` (Step 4).
- Existing service tests pin the current limits — they are the regression net
  for the behavior-preserving claim.
- Add one test that a sale item with a price above 1_000_000 still creates a
  sale (guards the documented no-cap divergence).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "for item in items:" services/sale_service.py services/purchase_service.py` returns no matches in `_insert_*_items` (the only remaining loops are in validation)
- [ ] `grep -rn "def validate_line_item\|def validate_item_count" utils/validation/item_validators.py` shows both
- [ ] New validator tests exist and pass
- [ ] Sale price-cap divergence is documented (docstring/comment in sale_service.py)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A service test fails because the shared validator's error message differs from
  the old inline message (update the test to the new message; if a test asserts
  a specific old message the maintainer wants preserved, report).
- The purchase quantity `quantity <= 0` check can't be mapped to
  `quantity_min=0.001` without changing behavior (the old check rejected 0.0
  and negatives; `validate_float(min_value=0.001)` does the same — verify).
- `models/enums.py` import into the validator creates a cycle (it won't —
  enums imports nothing — verify).

## Maintenance notes

- The sale price/quantity caps are intentionally absent — documented in
  `item_validators.py`. If the maintainer later decides to cap sale items,
  change the call site in `sale_service.py`, not the shared module.
- The purchase product-exists check remains a backlog item — when added, put it
  in `sale_service`'s post-validation step pattern.
- Executemany is now the only item-insert path; new item tables should follow
  it.