# Plan 017: `validate_money` must reject fractional values in string form

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat b0dd06a..HEAD -- utils/validation/validators.py tests/test_validation/test_validators.py services/product_service_support.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `b0dd06a`, 2026-08-15

## Why this matters

The invariant "Money is CLP integer-only" is enforced for floats but silently
bypassed for strings: `validate_money("999.6")` returns `1000` while
`validate_money(999.6)` raises. Verified by execution. The user-facing price
path (`services/product_service_support.py:57-64` → `validate_money_field`)
accepts dialog input, so a price typed as `999.6` is silently stored as 1000
CLP — the app alters user data instead of rejecting it. The sibling validator
`validate_integer` (validators.py:71-72) already rejects fractional strings,
so this is also an internal inconsistency. This plan makes `validate_money`
reject any value whose exact decimal form is not an integer.

## Current state

```python
# utils/validation/validators.py:148-182
def validate_money(
    value: Any, field_name: str = "Amount", max_value: int | None = 1_000_000
) -> int:
    """..."""
    try:
        # Check for non-integer floats before rounding
        if isinstance(value, float) and not value.is_integer():
            raise ValidationException(f"{field_name} cannot have decimals")

        money_value = int(round(float(value)))          # <-- strings round silently
        if not isinstance(money_value, int):
            raise ValidationException(f"{field_name} must be an integer")
        if money_value < 0:
            raise ValidationException(f"{field_name} cannot be negative")
        if max_value is not None and money_value > max_value:
            raise ValidationException(f"{field_name} cannot exceed {max_value:,} CLP")
        return money_value
    except (ValueError, TypeError):
        raise ValidationException(f"Invalid {field_name.lower()} value") from None
```

Behavior matrix today (verified by execution):

| Input | Today | After this plan |
|-------|-------|-----------------|
| `999` | 999 | 999 |
| `1000.0` (float) | 1000 | 1000 |
| `"1000"` (str) | 1000 | 1000 |
| `"999.6"` (str) | **1000 (silent round)** | raises `ValidationException` |
| `"1000000.4"` (str) | **1000000 (silent round)** | raises `ValidationException` |
| `999.6` (float) | raises | raises |

Callers: `validate_money` is used across service validation (product prices,
totals, etc.). `services/product_service_support.py:57-64` wraps it as
`validate_money_field` for the product price path. Before changing behavior,
grep all callers (below) and confirm no test relies on the rounding.

Repo conventions that apply:

- Validators raise `ValidationException` (from `utils/exceptions.py`) with
  clear Spanish/English messages; never silently coerce user data.
- Tests live in `tests/test_validation/test_validators.py` — class
  `TestValidators`, method `test_money_validation` at line 84.
- `Decimal` is the exact-arithmetic tool for the check; `str(value)` round-trip
  is exact for int/float/str/Decimal inputs.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Target tests | `.venv/bin/python -m pytest tests/test_validation/test_validators.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `utils/validation/validators.py` — `validate_money` only
- `tests/test_validation/test_validators.py` — extend `test_money_validation`

**Out of scope** (do NOT touch):
- `validate_money_multiplication` (validators.py:185) — the `int(round(...))`
  there is the legit CLP conversion of `price × quantity` and stays.
- `validate_float` / `validate_float_non_negative` — quantities keep 3 decimals.
- Any caller in `services/` — the new strictness must not require caller changes; if the full suite shows a caller depending on rounding, that's a STOP condition.

## Git workflow

- Branch: `advisor/017-money-decimal-strings`
- Commit message style follows the repo (`fix: ...`, `tests: ...` — see `git log --oneline -10`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Rewrite the integrality check with Decimal

In `utils/validation/validators.py`, replace the body of `validate_money`
with a Decimal-based check. Exact check first, then the existing bounds:

```python
from decimal import Decimal, InvalidOperation
# (add to the existing imports at the top of the file)

def validate_money(
    value: Any, field_name: str = "Amount", max_value: int | None = 1_000_000
) -> int:
    try:
        decimal_value = Decimal(str(value))
        if decimal_value != decimal_value.to_integral_value():
            raise ValidationException(f"{field_name} cannot have decimals")
        money_value = int(decimal_value)
        if money_value < 0:
            raise ValidationException(f"{field_name} cannot be negative")
        if max_value is not None and money_value > max_value:
            raise ValidationException(f"{field_name} cannot exceed {max_value:,} CLP")
        return money_value
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationException(f"Invalid {field_name.lower()} value") from None
```

Notes:
- `Decimal(str(value))` is exact for `int`, `float`, `str`, and `Decimal`
  inputs. `float 1000.0` → `Decimal("1000.0")` → integral → accepted,
  preserving current float behavior.
- `"1e3"` → `Decimal("1E+3")` → integral → 1000 (same as today's
  `int(round(float("1e3")))`).
- `float('nan')` / `float('inf')` → `Decimal("nan")` / `Decimal("Infinity")`
  → `InvalidOperation` → `ValidationException` (today they raise
  `ValueError` inside the try → same outcome).
- Drop the old `isinstance(value, float)` branch and the
  `int(round(float(value)))` line — the Decimal check subsumes both.

**Verify**: `.venv/bin/python -m pytest tests/test_validation/test_validators.py -k money` → passes.

### Step 2: Extend the money tests with string-fraction cases

In `tests/test_validation/test_validators.py`, inside
`test_money_validation` (line 84), add these cases (match the existing
assertion style — check the current method to copy its raises pattern):

- `validate_money("999.6")` → `pytest.raises(ValidationException)`
- `validate_money("1000000.4")` → raises
- `validate_money("1000.0")` → returns `1000` (integral string accepted — keep behavior consistent with float `1000.0`)
- `validate_money("1e3")` → returns `1000`
- `validate_money(1000.0)` → returns `1000` (unchanged)
- `validate_money("1000")` → returns `1000` (unchanged)

**Verify**: `.venv/bin/python -m pytest tests/test_validation/test_validators.py` → all pass.

### Step 3: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass (if a caller's test fails because it
  passed a fractional string and asserted the rounded result, that test is
  asserting the bug — per STOP conditions, report rather than rewrite it)
- `.venv/bin/ruff check .` → exit 0
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0

## Test plan

Step 2 extends `test_money_validation` with the six cases above. No new test
files. The full suite verifies no caller regressed.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "int(round(float" utils/validation/validators.py` returns nothing
- [ ] `utils/validation/validators.py` imports and uses `Decimal`
- [ ] `.venv/bin/python -m pytest tests/test_validation/test_validators.py` exits 0
- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts.
- A full-suite failure is caused by a caller or test that relied on the
  rounding (report the exact test; it may indicate a caller that needs an
  explicit decision).
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file.

## Maintenance notes

- `Decimal(str(value))` is the one place money inputs are converted; future
  money validators should reuse the same idiom instead of `float()` + round.
- A reviewer should scrutinize: that the error message for fractional strings
  is the same `"{field_name} cannot have decimals"` used by the float branch
  (it is — the message is unchanged), and that no caller passes `bool` values
  (a `bool` now raises `ValidationException`; today it returned 0/1 — grep
  callers for bools if the suite flags anything).
