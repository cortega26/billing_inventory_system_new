# Plan 043: Collapse dual validation systems — models delegate to validators.py

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- models/customer.py models/product.py models/sale.py models/purchase.py models/inventory.py models/category.py ui/customer_view.py ui/product_view.py utils/validation/validators.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: none (run BEFORE any future model/schema work)
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The same business rules are implemented twice: `utils/validation/validators.py`
(12 functions, used by the service layer) and ~17 `validate_*` methods spread
across the models (used on model construction, including every `from_db_row`
load, and by UI dialogs that validate by constructing a fake entity). The two
implementations already drift — e.g. `Customer.validate_name`
(`models/customer.py:140`) rejects punctuation that `validate_string`
(`validators.py:29`) allows, and `SaleItem.normalize_quantity` ROUNDS 4-decimal
input where `validate_float` REJECTS it. AGENTS.md makes `utils/validation/` the
owner of reusable validation primitives. This plan makes the models thin
wrappers over the validators module so a rule change is a single edit.

## Current state

- `models/customer.py:97-143` — `validate_identifier_9`, `validate_identifier_3or4`,
  `validate_name` duplicate `validators.py:265-278` + `validate_string`'s
  normalization/cap.
- `ui/customer_view.py:91-102` — `EditCustomerDialog.validate_and_accept`
  validates by constructing `Customer(id=0, ...)` ("Create a temporary customer
  to validate the input") then does a same-type `raise ValidationException(str(e)) from e`.
- `ui/product_view.py:138-141` — `validate_and_accept` calls
  `Product.validate_barcode` and re-raises `ValidationException(str(e)) from e`.
- `models/product.py:74-85` — `__init__` re-checks `cost_price`/`sell_price`
  are ints; `:87-91` `post_init_validation` runs `validate()` which re-checks
  the same; the module docstring (:1-5) says "Do not add @model_validator
  blocks" yet the file HAS one.
- `models/sale.py:88-111` — `SaleItem.normalize_quantity` (rounds 4-decimal
  input) and `validate_price`; `models/purchase.py:55-76` — `validate_quantity`
  and `validate_price` (same shape, slightly different message).
- `models/inventory.py:53` — `QUANTITY_PRECISION: ClassVar[int] = 3` (3rd copy;
  source is `models/enums.py:23`); `:79-91` `_validate_float_field` duplicates
  `validators.py:139-141`.
- `models/category.py:98-134` — `validate_name` re-implements `validate_string`
  normalization + length + its own `NAME_PATTERN` regex.

**Behavior notes (preserve exactly)**:
- `SaleItem.normalize_quantity` ROUNDS 4+ decimal input instead of rejecting —
  this is the model's load-path leniency. Keep the rounding; only re-express it
  via `validators.py` primitives if behavior is identical, otherwise leave the
  method body untouched.
- Model error messages are pinned by tests (`tests/test_models/`,
  `tests/test_validation/`). Delegating to validators.py changes some messages;
  update the tests that pin them — do NOT change the validators' messages.

**Repo conventions**:
- `utils/validation/validators.py` is the single source for validation
  primitives (AGENTS.md source-of-truth #2).
- Model construction runs `post_init_validation` on `from_db_row` — the
  consolidation must keep load-time behavior working for existing DB data.
- No new dependencies from `utils/validation/` → `models/` (validators import
  only `utils.exceptions` — keep it that way).

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Model tests | `.venv/bin/python -m pytest tests/test_models/` | all pass (after update) |
| Validation tests | `.venv/bin/python -m pytest tests/test_validation/` | all pass |
| Customer UI tests | `.venv/bin/python -m pytest tests/test_ui/test_customer_view.py tests/test_ui/test_product_view.py` | all pass (xvfb) |
| Services tests | `.venv/bin/python -m pytest tests/test_services/` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Schema drift | `.venv/bin/python scripts/check_schema_drift.py` | exit 0 |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `models/customer.py`, `models/product.py`, `models/sale.py`,
  `models/purchase.py`, `models/inventory.py`, `models/category.py`
- `ui/customer_view.py`, `ui/product_view.py`
- `utils/validation/validators.py` (ONLY if a small refactor is needed to let a
  model wrapper call it — otherwise untouched)
- `tests/test_models/`, `tests/test_validation/`, affected UI/service tests

**Out of scope**:
- Changing the behavior of `validate_float`/`validate_quantity` rounding vs
  rejection (the intentional leniency stays; only the duplication goes)
- `models/business.py` (no validate_* duplication found)
- The service-layer validators (already correct)

## Git workflow

- Branch: `advisor/043-validation-consolidation`
- Commit per logical unit (one per model).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Customer model + dialog

In `models/customer.py`, replace the bodies of the three static validators with
delegation (keep the method signatures and their `ValidationException`):
- `validate_identifier_9(identifier)` → `validate_9digit_identifier(identifier)`
- `validate_identifier_3or4(identifier)` → if not None,
  `validate_3or4digit_identifier(identifier)`
- `validate_name(name)` → `validate_string(name, min_length=1, max_length=50)`
  (note: this loosens the old char-whitelist regex to `validate_string`'s
  punctuation allowance — that is the INTENDED reconciliation; the regex
  whitelist was the drift).

In `ui/customer_view.py` `validate_and_accept` (:91-102): replace the
`Customer(id=0, ...)` construction with direct calls:
```python
validate_identifier_9(self.identifier_9_input.text().strip())
id3 = self.identifier_3or4_input.text().strip() or None
if id3 is not None:
    validate_3or4digit_identifier(id3)
name = self.name_input.text().strip() or None
if name is not None:
    validate_string(name, min_length=1, max_length=50)
self.accept()
```
Delete the redundant `try/except ValidationException as e: raise ... from e`
(the decorators `@ui_operation` + `@handle_exceptions(ValidationException, ...)`
already handle it — see `ui/sale_view.py:345` for the same pattern). Import the
validators from `utils.validation.validators`.

**Verify**: `.venv/bin/python -m pytest tests/test_models/test_customer_model.py tests/test_validation/test_validators.py tests/test_ui/test_customer_view.py` → pass (update tests that pinned the old messages).

### Step 2: Product model + dialog

In `models/product.py`:
- Delete the redundant int/bool checks in `__init__` (:76-82) — `post_init_validation`
  → `validate()` already enforces them.
- Rewrite the module docstring to state the real contract:
  `"""Models are data containers; business validation is enforced by services. Product.validate() runs at construction for load-path safety."""`
- Keep `validate_barcode` but make it delegate to a single barcode rule: move the
  rule to `utils/validation/validators.py` as `validate_barcode` (8/12/13/14
  digits) and have both the model and `ProductService._validate_barcode_format`
  (`services/product_service.py:404-436`) call it. Verify the service validator
  ALSO strips whitespace and requires `str` — fold those checks into the shared
  validator so both paths behave identically.

In `ui/product_view.py` `validate_and_accept` (:138-141): replace
`Product.validate_barcode` with the shared validator call; delete the
same-type `raise ValidationException(str(e)) from e` wrapper (decorators handle it).

**Verify**: `.venv/bin/python -m pytest tests/test_models/test_product.py tests/test_services/test_product_service.py tests/test_ui/test_product_view.py` → pass.

### Step 3: Sale/purchase price + quantity validators

In `models/sale.py` and `models/purchase.py`:
- `validate_price` / `SaleItem.validate_price`: delegate to `validate_money(price)`.
- Keep `SaleItem.normalize_quantity` and `PurchaseItem.validate_quantity` bodies
  UNCHANGED if their rounding-vs-reject semantics differ from `validate_quantity`
  (they do — see "Behavior notes"). If you find they are behaviorally identical
  to `validators.validate_quantity`, replace the body with the call.
- Update any test that pinned the old price message.

**Verify**: `.venv/bin/python -m pytest tests/test_models/ tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py` → pass.

### Step 4: Inventory model constant + float check

In `models/inventory.py`:
- Delete the `QUANTITY_PRECISION: ClassVar` (:53) and use
  `from models.enums import QUANTITY_PRECISION` in `_round_quantity` (:74-76).
  (Remove the now-unused `ClassVar` import if ruff flags it.)
- Replace `_validate_float_field`'s type+non-negative check with
  `validate_float_non_negative(value)` from `utils.validation.validators`,
  keeping the `MAX_QUANTITY` upper-bound check (that one has no validator
  equivalent — keep it inline).

**Verify**: `.venv/bin/python -m pytest tests/test_models/ tests/test_services/test_inventory_service.py` → pass. `grep -n "QUANTITY_PRECISION" models/inventory.py` shows the import.

### Step 5: Category model name validation

In `models/category.py`, re-express `validate_name` (:98-134) via
`validate_string(name, min_length=Category.NAME_MIN_LENGTH, max_length=Category.NAME_MAX_LENGTH)`
and keep the `NAME_PATTERN` check after it (that regex is category-specific and
has no validator.py equivalent — keep it inline). Preserve the exact messages.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_category_service.py` (and any category model tests) → pass.

### Step 6: Full verification

**Verify**: `.venv/bin/python scripts/check_schema_drift.py` → exit 0;
`.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .` → exit 0;
`.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Update `tests/test_models/` and `tests/test_validation/` for changed messages.
- Add one regression test in `tests/test_validation/` asserting the shared
  barcode validator rejects a 7-digit and a 15-digit barcode (guards the
  consolidated rule).
- The `Customer(id=0, ...)` dialog path: existing `tests/test_ui/test_customer_view.py`
  dialog tests cover it — ensure they still pass with direct validator calls.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -n "Customer(id=0" ui/customer_view.py` returns no matches
- [ ] `grep -n "QUANTITY_PRECISION: ClassVar" models/inventory.py` returns no matches
- [ ] `grep -n "Do not add @model_validator" models/product.py` returns no matches (docstring rewritten)
- [ ] `models/*.py` contain no hand-rolled decimal-counting or `not isinstance(x, int)` price checks (grep: `len(str_value.split("."))` and `"must be an integer (CLP"` return no matches in models/)
- [ ] New barcode validator regression test exists and passes
- [ ] `.venv/bin/python scripts/check_schema_drift.py` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- Delegating a model validator changes behavior on `from_db_row` loads such
  that existing DB data no longer constructs (report the data shape; do not
  loosen the validator to make it pass).
- `ProductService._validate_barcode_format` semantics differ from
  `Product.validate_barcode` beyond whitespace/str handling (read both before
  merging — if they differ materially, STOP and report).
- Adding an import from `models/` into `utils/validation/` is required (that
  direction is forbidden — validators must stay model-free).

## Maintenance notes

- The single validation source is now `utils/validation/validators.py`; model
  `validate_*` methods are thin wrappers that exist so `from_db_row` and
  `post_init_validation` keep working.
- The intentional leniency (model-side rounding of 4-decimal quantities on
  load) is documented in the model docstrings; if the team later decides to
  reject such data at load, change `normalize_quantity` and add a migration note.
- Reviewer should verify a real DB with historical data still loads every
  table (the suite's `db_manager` fixture uses SQLModel metadata; a spot-check
  against a copy of the live DB is recommended).