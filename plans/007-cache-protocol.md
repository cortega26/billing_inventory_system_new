# Plan 007: Unify the cache protocol; fix the false clear_cache pairing

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: the repo has uncommitted changes; the excerpts
> below reflect the working tree. Open each cited file and confirm the excerpt
> matches. On a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

The cache layer is fragmented and one claim is demonstrably false:

1. **`get_product_details` caching is broken AND mislabeled.** In
   `services/sale_service.py:796-799`:
   ```python
   @lru_cache(maxsize=100)  # noqa: B019 (intentional: paired with clear_cache)
   def get_product_details(self, product_id: int) -> dict[str, Any] | None:
   ```
   but `clear_cache` (`sale_service.py:458-461`) only clears
   `SaleService.get_all_sales.cache_clear()` — `get_product_details` is never
   cleared, so it can serve stale product prices forever after a product edit,
   and the `noqa` comment asserting the pairing is wrong.
2. **`lru_cache` on instance methods is near-useless.** The cache key includes
   `self`, so every view that constructs its own `SaleService()` (`ui/sale_view.py:498`)
   gets a fresh cache — the annotation is misleading either way.
3. **Five different `clear_cache` shapes exist**: instance method
   (`sale_service.py:458`, `product_service.py:351`, `customer_service.py:542`),
   classmethod (`InventoryService.clear_cache`, `CategoryService.clear_cache`),
   staticmethod delegating (`PurchaseService.clear_cache` → `PurchaseQueryService`),
   and the nine-line manual `AnalyticsService.clear_cache`
   (`analytics_service.py:320-331`). Callers mix `self.clear_cache()` and
   `Service.clear_cache()` arbitrarily.

This plan makes the protocol uniform and the invalidation complete — behavior
preserving, with a small correctness fix (product details now cleared).

## Current state

- `services/sale_service.py:458-461`:
  ```python
  def clear_cache(self):
      """Clear the sale cache."""
      SaleService.get_all_sales.cache_clear()
      logger.debug("Sale cache cleared")
  ```
- `services/sale_service.py:796-799` — `@lru_cache(maxsize=100)` on
  `get_product_details` (instance method, false pairing comment).
- `services/customer_service.py:542-545` — instance `clear_cache` →
  `self.get_all_customers.cache_clear()` (the `lru_cache` is on the instance
  method `get_all_customers`, `customer_service.py:205-208`).
- `services/product_service.py:351-354` — same shape (`get_all_products`,
  `maxsize=4`).
- `services/inventory_service.py` — `clear_cache` is a classmethod
  (`inventory_service.py:335`-ish; verify exact line when editing).
- `services/purchase_service.py:336`-ish — staticmethod delegating to
  `PurchaseQueryService.clear_cache()`.
- `services/analytics_service.py:320-331` — 9 manual `.cache_clear()` lines.
- `services/mutation_coordinator.py:23-24` — calls `InventoryService.clear_cache()`
  and `AnalyticsService.clear_cache()` (class-level).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Service tests | `.venv/bin/python -m pytest tests/test_services tests/test_critical_backend_flows.py -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `services/sale_service.py`, `services/customer_service.py`, `services/product_service.py`, `services/inventory_service.py`, `services/category_service.py`, `services/purchase_service.py`, `services/purchase_query_service.py`, `services/analytics_service.py`
- `tests/test_services/` (cache-freshness tests), `tests/test_critical_backend_flows.py`

**Out of scope**:
- `services/mutation_coordinator.py` — its calls are class-level and already correct; only verify it still works
- The `lru_cache` eviction semantics (maxsize) — keep them
- `ui/` — callers are `self.clear_cache()`/`Service.clear_cache()`; both keep working (see Step 3)

## Git workflow

- Branch: `advisor/007-cache-protocol`
- Commit messages: `fix: clear get_product_details cache on mutation`, `refactor: unify clear_cache protocol across services`
- Do NOT push unless instructed.

## Steps

### Step 1: Fix the actual bug

In `services/sale_service.py`:
- Either remove `@lru_cache` from `get_product_details` (simplest — it has no
  production callers today, grep-verified; only tests) OR add
  `SaleService.get_product_details.cache_clear()` to `clear_cache`.
  Prefer REMOVAL: the instance-keyed cache is near-useless anyway (see Why).
- Remove the false `# noqa: B019 ...` comment when the decorator goes.
- If you keep the decorator, ALSO move it to `@staticmethod`-compatible form or
  clear it in `clear_cache` — one of the two, and say which in the report.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py -q` → all pass. `grep -n "noqa: B019" services/sale_service.py` → no match if you removed it.

### Step 2: Standardize the protocol

Make every service's `clear_cache` a **classmethod with an identical signature**:

```python
@classmethod
def clear_cache(cls) -> None:
    cls._get_all_sales_cache_clear()  # per-service body, existing behavior
```

For each service, convert `def clear_cache(self)` → `@classmethod
def clear_cache(cls)` keeping the SAME body semantics (cache_clear targets stay
unchanged — for instance-keyed `lru_cache`, `.cache_clear()` works the same via
the class attribute). Update `AnalyticsService.clear_cache` to stay a
staticmethod or classmethod (match the rest; its nine lines are fine, just the
decorator shape changes). Do NOT change what is cleared — only the calling shape.

**Verify**: `.venv/bin/python -m pytest tests/test_services tests/test_critical_backend_flows.py -q` → all pass.

### Step 3: Fix call sites

Find every `self.clear_cache()` and `Service.clear_cache()` call
(`grep -rn "clear_cache()" services/ ui/`) and normalize to class-level calls
(`<ServiceClass>.clear_cache()`) OR keep instance calls where they already work
(both work once the methods are classmethods — a classmethod callable via
instance is valid Python). Only fix call sites that would BREAK; leave cosmetic
mixed usage alone (the protocol is now uniform even if call syntax varies).

**Verify**: `grep -rn "clear_cache" services/ | wc -l` recorded; suite green.

### Step 4: Regression tests

Add one cache-freshness test per mutated entity, following the pattern of
`tests/test_services/test_analytics_service.py:59` (pre-test cache hygiene) and
the sale-signal tests added by plan 008 (if 008 already landed, extend its
cache test; otherwise write standalone):

- Sale: `get_all_sales()` → create sale → `get_all_sales()` returns the new row.
- Product: `get_all_products()` → update product → fresh data.
- Product details: `get_product_details(id)` → update product price →
  `get_product_details(id)` reflects the new price (this test FAILS before
  Step 1 and passes after — it is the regression pin).

**Verify**: new tests pass; the product-details test fails on the pre-Step-1
code (confirm by running it against a stash, or note the reasoning in the report).

## Test plan

- The three cache-freshness tests above (sale, product list, product details).
- Existing suite must stay green — the protocol change is shape-only.

## Done criteria

- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `grep -n "noqa: B019" services/sale_service.py` → no matches
- [ ] `get_product_details` is either cache-free or cleared by `clear_cache` (verify by code + the new test)
- [ ] All `clear_cache` definitions are classmethods (grep `def clear_cache` → all preceded by `@classmethod`)
- [ ] The product-details freshness test exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] No files outside the in-scope list are modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- Converting a `clear_cache` to classmethod breaks a call site in a way the
  suite does not catch (e.g., a UI file calls it with an instance binding that
  fails) — STOP and report the site; do not widen scope to ui/ silently.
- A service's cache is not `lru_cache`-based (e.g., a hand-rolled dict cache) —
  STOP and report; the conversion assumes `cache_clear()` exists.
- `get_product_details` has a production caller you discover that plan 011's
  grep missed — STOP and report before removing the decorator.

## Maintenance notes

- Plan 008's cache-freshness tests depend on this plan's contract — run 008
  after 007.
- New services: copy the classmethod `clear_cache` shape; the coordinator calls
  class-level methods.
- Reviewer: confirm no cache-clearing behavior changed — only shapes.
