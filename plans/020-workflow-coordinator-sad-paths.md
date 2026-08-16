# Plan 020: Sad-path test coverage for the update-sale workflow and MutationCoordinator

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat b0dd06a..HEAD -- services/update_sale_workflow.py services/mutation_coordinator.py tests/test_services/test_ux_features.py tests/test_services/test_sale_service.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (runs independently; do it before any future refactor of `update_sale_workflow.py`)
- **Category**: tests
- **Planned at**: commit `b0dd06a`, 2026-08-15

## Why this matters

Two of the highest-risk money paths have no sad-path coverage:

1. `UpdateSaleWorkflow` — the multi-product stock-swap logic
   (`_validate_inventory_for_sale_update`) aggregates per-product old/new
   quantities so that a swap can succeed when product B's stock only suffices
   *after* product A is restored. This exact scenario historically
   double-restored inventory (commit `86063b1` "prevent double inventory
   restore"), yet every existing update test is single-product.
2. `MutationCoordinator.finalize_mutation` — the standardized post-commit
   finalization that every sale/purchase/adjustment route depends on — swallows
   cache-clear and event-emit exceptions with `try/except` + log. Its only test
   covers the happy path, so a silently failing coordinator (stale cache,
   missing UI refresh) would go unnoticed.

This plan adds the missing tests only — no production code changes.

## Current state

`services/update_sale_workflow.py` — the full validation block (lines 106-137):

```python
def _validate_inventory_for_sale_update(
    self, old_items: list[Any], new_items: list[dict[str, Any]]
) -> None:
    """
    Pre-validate stock for sale updates before opening a transaction.
    """
    old_quantities: dict[int, float] = {}
    for item in old_items:
        product_id = int(getattr(item, "product_id", 0))
        quantity = float(getattr(item, "quantity", 0.0))
        old_quantities[product_id] = old_quantities.get(product_id, 0.0) + quantity

    new_quantities: dict[int, float] = {}
    for item in new_items:
        product_id = int(item["product_id"])
        quantity = float(item["quantity"])
        new_quantities[product_id] = new_quantities.get(product_id, 0.0) + quantity

    for product_id, required_quantity in new_quantities.items():
        inventory = InventoryService.get_inventory(product_id)
        current_quantity = float(inventory.quantity) if inventory else 0.0
        restored_quantity = current_quantity + old_quantities.get(product_id, 0.0)
        available_after_update = round(
            restored_quantity - required_quantity, QUANTITY_PRECISION
        )

        if available_after_update < 0:
            raise ValidationException(
                "Insufficient inventory to update sale for product "
                f"{product_id}. Available after restore: {restored_quantity}, "
                f"required: {required_quantity}."
            )
```

The workflow transaction (`:57-92`): revert old stock → `_update_sale` →
`_update_sale_items` (delete + reinsert) → deduct new stock → audit; then
post-commit `MutationCoordinator.finalize_mutation` (`:99-104`).

`services/mutation_coordinator.py` (entire file, lines 10-60):

```python
class MutationCoordinator:
    @staticmethod
    def finalize_mutation(
        entity_id: int,
        items: list[Any],
        signal: Any,
        service_cache_clear_fn: Callable[[], None] | None = None,
    ) -> None:
        # 1. Clear core caches
        InventoryService.clear_cache()
        AnalyticsService.clear_cache()
        # 2. Clear specific service caches if provided
        if service_cache_clear_fn:
            try:
                service_cache_clear_fn()
            except Exception as e:
                logger.error(f"Error clearing service cache: {e}")
        # 3. Emit inventory changed events for affected products
        product_ids = MutationCoordinator._get_product_ids(items)
        for product_id in product_ids:
            try:
                event_system.inventory_changed.emit(product_id)
            except Exception as e:
                logger.error(...)
        # 4. Emit specific signal
        try:
            signal.emit(entity_id)
        except Exception as e:
            logger.error(f"Error emitting signal {signal}: {e}")
```

Existing test patterns to follow:

- `tests/test_services/test_ux_features.py` — `TestUXFeatures` class with
  `@pytest.fixture(autouse=True) setup(self, db_manager)` instantiating the
  services, plus a `capture_signal(signal)` helper (lines 14-21) that returns
  `(payloads, handler)` and connects a real listener; the existing coordinator
  test (lines 104-126) disconnects handlers in a `finally`.
- `tests/test_services/test_sale_service.py` — module-level fixtures
  `sale_service` / `product_service` / `customer_service` / `inventory_service`
  / `sample_category` / `sample_product` / `sample_customer` /
  `sample_sale_data` (lines 25-95); update tests route through
  `sale_service.update_sale(...)` which delegates to the workflow (lines
  335-340). Existing update tests: `test_update_sale_rolls_back_on_insufficient_inventory`
  (line 269), `test_update_sale_insufficient_inventory_fails_before_mutation`
  (line 296), `test_update_sale_emits_sale_updated_once` (line 383).
- Real-DB `db_manager` fixture comes from `tests/conftest.py:22-49`; every
  test gets a fresh in-memory schema.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| New workflow tests | `.venv/bin/python -m pytest tests/test_services/test_update_sale_workflow.py` | all pass |
| Coordinator tests | `.venv/bin/python -m pytest tests/test_services/test_ux_features.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `tests/test_services/test_update_sale_workflow.py` — NEW file
- `tests/test_services/test_ux_features.py` — add coordinator failure tests

**Out of scope** (do NOT touch):
- `services/update_sale_workflow.py`, `services/mutation_coordinator.py` — no production changes; if a test exposes a real bug, STOP and report.
- `tests/test_services/test_sale_service.py` — do not modify existing tests (the new workflow file covers the new scenarios; existing tests already cover single-product paths).
- Any other file.

## Git workflow

- Branch: `advisor/020-workflow-coordinator-sad-paths`
- Commit per step; message style follows the repo (`tests: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Create the workflow test file

Create `tests/test_services/test_update_sale_workflow.py`. Copy the fixture
block from `tests/test_services/test_sale_service.py:25-95` verbatim
(module-level `sale_service`, `product_service`, `customer_service`,
`inventory_service`, `category_service`, `sample_category`, `sample_product`,
`sample_customer`, `sample_sale_data` fixtures — including the
`from services.category_service import CategoryService` import placed after
the earlier fixtures, exactly as the source file does). The new file also
needs the module header imports from the source file that the fixtures
depend on: `from datetime import date`, `import pytest`,
`from database.database_manager import DatabaseManager`, the six service
imports, and `from utils.exceptions import ValidationException` — plus the
`capture_signal` helper copied from `test_ux_features.py:14-21`.

Add the following test methods:

```python
def test_two_product_swap_requires_restored_stock_validation(
    self, sale_service, sample_sale_data, inventory_service, sample_product,
    product_service, sample_category
):
    # Product A (sample_product) sold 2; product B has only 1 in stock.
    # The update swaps to B(2): B's stock is insufficient even after A's
    # restore, so the update must fail BEFORE any mutation.
    b_id = product_service.create_product({
        "name": "Product B",
        "barcode": "87654321",
        "category_id": sample_category.id,
        "cost_price": 500,
        "sell_price": 1000,
    })
    inventory_service.update_quantity(b_id, 1.0)
    inventory_service.update_quantity(sample_product.id, 10.0)
    sale_id = sale_service.create_sale(**sample_sale_data)

    swapped = [
        {"product_id": b_id, "quantity": 2, "sell_price": 1000, "profit": 1000}
    ]

    with pytest.raises(ValidationException, match="Insufficient inventory"):
        sale_service.update_sale(sale_id, sample_sale_data["customer_id"],
                                 sample_sale_data["date"], swapped)

    # No partial writes: sale still has product A, inventory untouched.
    sale = sale_service.get_sale(sale_id)
    assert len(sale.items) == 1
    assert sale.items[0].product_id == sample_product.id
    assert inventory_service.get_inventory(sample_product.id).quantity == 8.0
    assert inventory_service.get_inventory(b_id).quantity == 1.0
```

```python
def test_two_product_swap_succeeds_when_stock_allows_after_restore(
    self, sale_service, sample_sale_data, inventory_service, sample_product,
    product_service, sample_category
):
    # B has exactly 2 units; available after A's restore is 2 + 0 = 2 -> OK.
    b_id = product_service.create_product({
        "name": "Product B",
        "barcode": "87654321",
        "category_id": sample_category.id,
        "cost_price": 500,
        "sell_price": 1000,
    })
    inventory_service.update_quantity(b_id, 2.0)
    inventory_service.update_quantity(sample_product.id, 10.0)
    sale_id = sale_service.create_sale(**sample_sale_data)

    sale_payloads, sale_handler = capture_signal(event_system.sale_updated)
    inv_payloads, inv_handler = capture_signal(event_system.inventory_changed)
    try:
        swapped = [
            {"product_id": b_id, "quantity": 2, "sell_price": 1000, "profit": 1000}
        ]
        sale_service.update_sale(sale_id, sample_sale_data["customer_id"],
                                 sample_sale_data["date"], swapped)

        sale = sale_service.get_sale(sale_id)
        assert len(sale.items) == 1
        assert sale.items[0].product_id == b_id
        assert sale.items[0].quantity == 2.0
        # A fully restored, B deducted exactly once.
        assert inventory_service.get_inventory(sample_product.id).quantity == 10.0
        assert inventory_service.get_inventory(b_id).quantity == 0.0
        # Events emitted exactly once, after commit.
        assert sale_payloads == [sale_id]
        assert inv_payloads.count(b_id) == 1
    finally:
        event_system.sale_updated.disconnect(sale_handler)
        event_system.inventory_changed.disconnect(inv_handler)
```

```python
def test_update_sale_insufficient_stock_leaves_no_partial_writes(
    self, sale_service, sample_sale_data, inventory_service, sample_product
):
    # Single product over-request: A sold 2 from 10; request 11 (only 10
    # available after restore) -> fail, nothing mutated.
    inventory_service.update_quantity(sample_product.id, 10.0)
    sale_id = sale_service.create_sale(**sample_sale_data)

    oversized = [
        {"product_id": sample_product.id, "quantity": 11,
         "sell_price": sample_product.sell_price,
         "profit": 11 * (sample_product.sell_price - sample_product.cost_price)}
    ]
    with pytest.raises(ValidationException, match="Insufficient inventory"):
        sale_service.update_sale(sale_id, sample_sale_data["customer_id"],
                                 sample_sale_data["date"], oversized)

    sale = sale_service.get_sale(sale_id)
    assert len(sale.items) == 1
    assert sale.items[0].quantity == 2.0
    assert inventory_service.get_inventory(sample_product.id).quantity == 8.0
```

Notes:
- Use `sale_service.update_sale(...)` (public API, routes through the
  workflow) — do not instantiate `UpdateSaleWorkflow` directly unless a test
  needs internals; the public route is the integration surface.
- Follow the repo's import style in the new file (imports at top; the
  `category_service` import placement must mirror the source file to avoid
  ruff E402).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_update_sale_workflow.py` → 3 passed.

### Step 2: Add coordinator failure-injection tests

In `tests/test_services/test_ux_features.py`, inside `TestUXFeatures`, add:

```python
def test_finalize_mutation_swallows_cache_clear_failure(self):
    def broken_cache_clear():
        raise RuntimeError("cache boom")

    inv_payloads, inv_handler = capture_signal(event_system.inventory_changed)
    sale_payloads, sale_handler = capture_signal(event_system.sale_added)
    try:
        # Must NOT raise; the other finalization steps still run.
        MutationCoordinator.finalize_mutation(
            entity_id=7,
            items=[{"product_id": 1}],
            signal=event_system.sale_added,
            service_cache_clear_fn=broken_cache_clear,
        )
        assert inv_payloads == [1]
        assert sale_payloads == [7]
    finally:
        event_system.inventory_changed.disconnect(inv_handler)
        event_system.sale_added.disconnect(sale_handler)

def test_finalize_mutation_swallows_signal_failure(self):
    inv_payloads, inv_handler = capture_signal(event_system.inventory_changed)

    class BrokenSignal:
        # finalize_mutation only calls signal.emit(entity_id) — a plain
        # object with an emit method is a sufficient duck-typed signal.
        def emit(self, *args, **kwargs):
            raise RuntimeError("signal boom")

    try:
        # Must NOT raise; inventory events still emitted.
        MutationCoordinator.finalize_mutation(
            entity_id=9,
            items=[{"product_id": 2}],
            signal=BrokenSignal(),
        )
        assert inv_payloads == [2]
    finally:
        event_system.inventory_changed.disconnect(inv_handler)
```

Note: `finalize_mutation` only calls `signal.emit(entity_id)` (see the excerpt
above), so the duck-typed `BrokenSignal` class is the correct construct — do
NOT try to subclass anything from `utils/system/event_system.py`; its signal
objects are PySide6 `Signal` or the headless `MockSignal`, neither of which is
a suitable subclassing base.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_ux_features.py` → all pass, including the two new tests.

### Step 3: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0

## Test plan

| Test | File | Case |
|------|------|------|
| test_two_product_swap_requires_restored_stock_validation | test_update_sale_workflow.py | swap with insufficient B stock → ValidationException before mutation; no partial writes |
| test_two_product_swap_succeeds_when_stock_allows_after_restore | test_update_sale_workflow.py | swap with sufficient B stock → A fully restored, B deducted exactly once, events emitted once |
| test_update_sale_insufficient_stock_leaves_no_partial_writes | test_update_sale_workflow.py | oversized quantity → raise; sale items and inventory untouched |
| test_finalize_mutation_swallows_cache_clear_failure | test_ux_features.py | cache-clear raises → no exception; events still emitted |
| test_finalize_mutation_swallows_signal_failure | test_ux_features.py | signal emit raises → no exception; inventory events still emitted |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `tests/test_services/test_update_sale_workflow.py` exists and contains the 3 tests above
- [ ] `tests/test_services/test_ux_features.py` contains the 2 new coordinator tests
- [ ] `.venv/bin/python -m pytest tests/test_services/test_update_sale_workflow.py tests/test_services/test_ux_features.py` → 5 new tests pass
- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `git diff --stat services/` is empty (no production code changed)
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts.
- A new test exposes a production bug (e.g. double restore or a raised
  exception escaping `finalize_mutation`). Report it with the failing
  assertion — do NOT fix production code as part of this plan.
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- These tests are the characterization layer for `update_sale_workflow.py` —
  future refactors of the workflow (e.g. plan for receipt_id regeneration, or
  switching to the mutation coordinator) must keep these passing, and new
  multi-product behaviors should be added here.
- The coordinator tests pin the "swallow + continue" contract; if that policy
  ever changes (fail loud), these tests must be updated deliberately.
- A reviewer should scrutinize: that the swap tests assert *exactly-once*
  inventory effects (the historical double-restore bug class) and that no
  test depends on test ordering (`pytest-randomly` shuffles).
