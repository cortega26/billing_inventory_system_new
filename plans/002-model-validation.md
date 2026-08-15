# Plan 002: Unify model validation — service-layer enforcement, no load-time crashes

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

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

Two related defects share one root cause: model validation is inconsistently
wired.

1. **Validators are dead code on most construction paths.** SQLModel
   `table=True` models do NOT run `@model_validator(mode="after")` blocks in
   `__init__`. Verified empirically: `SaleItem(quantity=-5)` and
   `Sale(date=2099-01-01, total_amount=-100)` both construct silently. The
   validators in `models/sale.py:59-64,188-197`, `models/purchase.py:39-43,116-123`,
   `models/customer.py:60-70`, `models/inventory.py:56-71` are dead weight —
   but they LOOK like enforcement, so no one notices the service layer never
   re-checks. Concretely, `CustomerService.create_customer`
   (`services/customer_service.py:51-53`) "validates" the name by constructing
   `Customer(...)` — a no-op. Verified: a 208-char `<script>`-laden name was
   stored.
2. **The one model that DOES validate on construction breaks list loads.**
   `models/product.py:68-81` calls `self.validate()` from `__init__`, and
   `from_db_row` goes through `__init__` (`models/product.py:145-170`).
   `validate()` raises when `cost_price`/`sell_price` > `MAX_PRICE_CLP`
   (`models/product.py:88-119`). One out-of-range legacy row therefore makes
   `get_all_products` fail wholesale (`services/product_service.py:102-112`
   wraps it in `DatabaseException`), bricking the products tab and the
   sale/purchase product pickers. The repo even ships a legacy DB with such
   rows (`billing_inventory.windows-import-20260405.db`).

The fix direction: **models load raw data; services validate before mutation.**
This matches AGENTS.md ("services/ ... define application-level validation ...
that are not fully enforced in SQLite" and "Do not bypass service-layer
validation").

## Current state

- `models/product.py:68-81` — `Product.__init__` pops `category_name`, then calls
  `self.validate()` (the ONLY model that validates at construction).
- `models/sale.py:55-64` — `SaleItem.post_init_validation` (`@model_validator(mode="after")`)
  — does not run at construction (verified).
- `models/sale.py:188-197` — `Sale.post_init_validation` — same.
- `models/customer.py:60-70` — `Customer` validator; `create_customer` relies on
  construction (`services/customer_service.py:51-53`):
  ```python
  if name is not None:
      temp_customer = Customer(id=0, identifier_9="900000000", name=name)
      name = temp_customer.name  # This will be the normalized version
  ```
- `schema.sql:31-39` — `customers` table has CHECKs only on `identifier_9`, none
  on `name`; so DB-level fallback is absent for the name rule.
- `services/product_service.py:395-450` — `create_product`/`update_product`
  validate prices explicitly (they call validators, not the model) — the pattern
  that already works and must be extended to the customer name.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Validation tests | `.venv/bin/python -m pytest tests/test_validation tests/test_services/test_customer_service.py tests/test_services/test_product_service.py -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `models/product.py`, `models/sale.py`, `models/purchase.py`, `models/customer.py`, `models/inventory.py` — validation wiring only
- `services/customer_service.py` — `create_customer` name validation
- `tests/test_validation/test_validators.py`, `tests/test_services/test_customer_service.py`, `tests/test_services/test_product_service.py`, `tests/test_models/test_product.py`

**Out of scope**:
- `models/category.py`, `models/audit_log.py` — no validators to rewire
- `schema.sql` CHECK additions — plan 004 owns schema changes; do not touch schema here
- Service mutation paths other than `create_customer` (do not audit-and-fix
  every service in this plan — only what the verification steps below cover)

## Git workflow

- Branch: `advisor/002-model-validation`
- Commit message style: `fix: enforce customer name validation at service layer; stop validating on product load`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Confirm the behavior (characterization)

Run this snippet and record the output in your report (it must match the
excerpts):

```bash
.venv/bin/python - <<'EOF'
from models.sale import Sale, SaleItem
from models.customer import Customer
try:
    SaleItem(quantity=-5, sale_id=1, product_id=1, unit_price=100, profit=0)
    print("SaleItem(-5): CONSTRUCTED (bug confirmed)")
except Exception as e:
    print("SaleItem(-5): rejected:", type(e).__name__)
try:
    Customer(id=0, identifier_9="900000000", name="x"*208)
    print("Customer(208-char name): CONSTRUCTED (bug confirmed)")
except Exception as e:
    print("Customer: rejected:", type(e).__name__)
EOF
```

**Verify**: both lines print "CONSTRUCTED (bug confirmed)". If either prints
"rejected", STOP — the code has changed since this plan was written.

### Step 2: Make customer name validation real

In `services/customer_service.py::create_customer`, replace the construction
no-op with an explicit validation call. Find the repo's name validation
primitive (check `utils/validation/validators.py` for a name/string validator —
e.g. `validate_string` with `max_length=50`, matching `schema.sql`'s
`LENGTH(name) <= 50` intent; also check how `update_customer` validates the
name, and mirror it exactly). Keep the normalization behavior (`temp_customer.name`
sanitization) if `update_customer` preserves it — the point is to enforce the
rule, not change normalization.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_customer_service.py -q` → all pass.

### Step 3: Remove construction-time validation from Product

In `models/product.py:68-81`, remove the `self.validate()` call from `__init__`
(keep the `category_name` handling and the price-type checks — those are cheap
and safe — or move all of it; the decision is: **no business-rule validation at
construction**). Keep `validate()` as a public method (services or tests may
call it explicitly). Verify that `create_product`/`update_product` call
`validate()` or the individual validators explicitly — if they relied on the
model's `__init__` validation, add the explicit call in the service
(`services/product_service.py:395-450`). Check `tests/test_models/test_product.py`
and `tests/test_validation/test_validators.py` for tests asserting
`Product(...)` raises — those tests encode the old behavior; update them to
construct the model and call `.validate()` (or assert the service path raises).

**Verify**: `.venv/bin/python -m pytest tests/test_validation tests/test_services/test_product_service.py tests/test_models/test_product.py -q` → all pass after updating the stale assertions.

### Step 4: Add the load-time isolation regression test

In `tests/test_services/test_product_service.py`, add a test: insert a product
with `sell_price = 2_000_000` directly via `DatabaseManager.execute_query`
(following the existing test patterns in that file), then assert
`get_all_products()` succeeds and returns the row (log-and-load, no raise). This
pins the fix for the bricks-the-list bug.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_product_service.py -q` → all pass, including the new test.

### Step 5: Document the validation contract

In `models/__init__.py`-adjacent docs or a module docstring in
`models/product.py` (short, 2-3 lines): "Models are data containers; business
validation is enforced by services. Do not add `@model_validator` blocks
expecting them to run at construction — SQLModel `table=True` skips them."

**Verify**: no verification command; keep it a docstring only.

## Test plan

- Update: any test asserting `Product(...)` or `Sale(...)` raises at
  construction → assert the service/validator path instead.
- New: `get_all_products` survives an out-of-range legacy row (Step 4).
- New: `create_customer` rejects name > 50 chars with `ValidationException`
  (mirror the existing `test_validation` patterns).
- Pattern: `tests/test_services/test_product_service.py` and
  `tests/test_validation/test_validators.py` are the structural exemplars.

## Done criteria

- [ ] Step 1 snippet now shows the two constructs no longer silently pass where services must catch them (i.e., service-level tests reject invalid input)
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] No `self.validate()` call remains in `models/product.py::__init__`
- [ ] `create_customer` explicitly validates the name (grep shows the validator call)
- [ ] The new out-of-range-row test exists and passes
- [ ] No files outside the in-scope list are modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- Step 1 output does not confirm the bug (code has drifted).
- `update_customer`'s name validation differs materially from what Step 2 needs
  (e.g., it validates nothing either) — then STOP and report; the plan needs a
  decision on where name rules live.
- Removing `Product.__init__` validation breaks a service path not covered by
  the in-scope tests — STOP and report which path, do not widen the scope
  silently.

## Maintenance notes

- Future model fields: the "models are containers" contract means new rules go
  in validators + service calls, never in `@model_validator` blocks expecting
  construction-time enforcement.
- The `db_manager` test fixture builds the DB from `SQLModel.metadata`, so
  `schema.sql` CHECK gaps (customers.name) stay invisible in tests — plan 004's
  drift check extension is the long-term guard.
- Reviewer: confirm no service mutation path lost validation coverage in Step 3
  (grep for `validate()` usage in `services/product_service.py`).
