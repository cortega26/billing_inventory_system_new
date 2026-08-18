# Plan 053: Shared model datetime parsing; delete dead Sale/Purchase mutators

> **AMENDMENT 2026-08-17 (executor STOP → plan defect)**: the plan's claim that
> ALL Sale/Purchase mutators have no callers was FALSE for
> `Purchase.recalculate_total` — it has a LIVE production caller at
> `models/purchase.py:123` inside `post_init_validation`
> (`self.recalculate_total()`), reachable via `Purchase.model_validate(...)`.
> REVISED SCOPE for Step 3: KEEP `Purchase.recalculate_total` (live — do not
> delete, do not touch `post_init_validation`). Delete ONLY the verified-dead
> mutators: Sale's `add_item`, `remove_item`, `recalculate_total`, `update_date`,
> `update_customer` AND Purchase's `add_item`, `remove_item`, `update_date`
> (grep-verify each has no production or test caller before deleting; note:
> `Purchase` has NO `update_customer` — the plan's premise was wrong on that
> too). Update the done-criteria grep to exclude the kept
> `Purchase.recalculate_total`. Steps 1/2/4 (the datetime helper extraction and
> its tests) are already DONE and committed on the branch.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- utils/dates.py models/sale.py models/purchase.py models/product.py models/inventory.py models/category.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S-M
- **Risk**: LOW-MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

Two DRY smells in the models: (1) the identical expression
`datetime.fromisoformat(row["created_at"]) if "created_at" in row and row["created_at"] else datetime.now()`
appears 8 times across 5 models (`sale`, `purchase`, `product` ×2, `inventory`
×2, `category` ×2), and the `strptime("%Y-%m-%d")` → `fromisoformat` fallback
appears twice — a schema change (e.g. plan-004-style normalization) forces
edits in 6+ places in lockstep; (2) `Sale` and `Purchase` carry twin mutator
methods (`add_item`, `remove_item`, `recalculate_total`, `update_date`,
`update_customer`) that are drift twins with subtly different semantics (sale's
`remove_item` silently filters, purchase's raises). Most are dead; one
(`Purchase.recalculate_total`) is kept because `Purchase.post_init_validation`
calls it. This plan extracts the datetime parsing into a Qt-free helper module
and deletes the dead mutators.

## Current state

- Datetime sites (grep-verified): `models/inventory.py:104,109`;
  `models/sale.py:78,221` (+ `:204-206` date fallback);
  `models/purchase.py:140` (+ `:130-132` date fallback); `models/product.py:166,171`;
  `models/category.py:62,67`.
- Dead mutators: `models/sale.py:262-289` (`add_item`, `remove_item`,
  `recalculate_total`, `update_date`, `update_customer`); `models/purchase.py`
  has the same set (verify lines; `grep -n "def add_item\|def remove_item\|def recalculate_total\|def update_date\|def update_customer" models/purchase.py`).
- Note: `models/inventory.py` also has `update_quantity`/`set_quantity`/`clone`/
  `create_empty` — do NOT delete those (they are exercised by the `db_manager`
  fixture and model tests; only the Sale/Purchase mutators are dead).

**Repo conventions**:
- Models import only Qt-free utils (`utils.exceptions`, `utils.system.logger`,
  `utils.validation.validators`) — the new date helpers must live in a Qt-free
  module (`utils/dates.py`), NOT `utils/helpers.py` (which imports PySide6).
- Any public method must have a caller or a test (plan-011 rule).

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Model tests | `.venv/bin/python -m pytest tests/test_models/` | all pass |
| Service tests | `.venv/bin/python -m pytest tests/test_services/ tests/test_critical_backend_flows.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `utils/dates.py` (new)
- `models/sale.py`, `models/purchase.py`, `models/product.py`,
  `models/inventory.py`, `models/category.py`
- `tests/test_utils/` (new tests) and any test that calls the deleted mutators

**Out of scope**:
- `models/inventory.py`'s `update_quantity`/`set_quantity`/`clone`/`create_empty`
  (live — keep)
- The `from_db_row` mapping logic beyond the datetime expressions
- Model `to_dict` datetime formatting (they use `isoformat()` correctly)

## Git workflow

- Branch: `advisor/053-model-date-helpers`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Create utils/dates.py

Create `utils/dates.py` (Qt-free):

```python
from datetime import datetime

def parse_datetime_cell(row: dict, key: str) -> datetime:
    """Parse a nullable ISO-8601 datetime cell, falling back to now when absent."""
    value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    if value:
        return datetime.fromisoformat(value)
    return datetime.now()

def parse_date_cell(row: dict, key: str) -> datetime:
    """Parse a date cell, accepting 'YYYY-MM-DD' or ISO-8601 forms."""
    value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    if not value:
        return datetime.now()
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return datetime.fromisoformat(value)
```

**Verify**: `.venv/bin/python -c "import utils.dates"` → exit 0.

### Step 2: Use the helpers in the models

Replace the inline expressions in each model's `from_db_row`:
- `models/sale.py:78,221` — `created_at=parse_datetime_cell(row, "created_at")`.
- `models/sale.py:204-206` — `date_val = parse_date_cell(row, "date")`.
- `models/purchase.py:140` — `created_at=parse_datetime_cell(row, "created_at")`;
  `:130-132` — `date_val = parse_date_cell(row, "date")`.
- `models/product.py:166,171` — `created_at=parse_datetime_cell(row, "created_at")`,
  `updated_at=parse_datetime_cell(row, "updated_at")`.
- `models/inventory.py:104,109` — same for created_at/updated_at.
- `models/category.py:62,67` — same.

Add `from utils.dates import parse_datetime_cell, parse_date_cell` to each file;
remove the now-unused `from datetime import datetime` import if ruff flags it.

**Verify**: `grep -rn "fromisoformat(row\|strptime(row" models/` → no matches.
`.venv/bin/python -m pytest tests/test_models/ tests/test_services/` → all pass.

### Step 3: Delete the dead Sale/Purchase mutators (AMENDED)

In `models/sale.py`, delete `add_item`, `remove_item`, `recalculate_total`,
`update_date`, `update_customer` (:262-289) — ALL verified dead (no production
or test callers).
In `models/purchase.py`, delete `add_item`, `remove_item`, `update_date`
(grep-verify each has no caller first). **KEEP `Purchase.recalculate_total`** —
it has a live caller at `models/purchase.py:123` (`post_init_validation`); do
NOT modify `post_init_validation`.
Confirm with: `grep -rn "\.add_item(\|\.remove_item(\|\.update_date(\|\.update_customer(" --include="*.py" ui/ services/ tests/ models/`
→ no matches (the UI hits at `ui/sale_view.py:232,260,266` are the VIEW's own
`add_item` method, not the model's — confirm the call targets by reading them).
`Sale.recalculate_total` and `Purchase.recalculate_total` are the ONLY remaining
`recalculate_total` definitions.

**Verify**: `.venv/bin/python -m pytest tests/test_models/` → all pass (no test
pinned the mutators). `.venv/bin/python -m pytest` → all pass.

### Step 4: Add helper tests

Add `tests/test_utils/test_dates.py` covering: `parse_datetime_cell` parses an
ISO string and falls back to a datetime when the cell is empty; `parse_date_cell`
parses both `"2026-08-17"` and an ISO-8601 timestamp.

**Verify**: `.venv/bin/python -m pytest tests/test_utils/test_dates.py` → pass.

### Step 5: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- New `tests/test_utils/test_dates.py` (Step 4).
- Existing model/service suites cover `from_db_row` for every model — the
  regression net for the datetime refactor.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "fromisoformat(row\|strptime(row" models/` returns no matches
- [ ] `grep -rn "def add_item\|def remove_item\|def update_date\|def update_customer" models/sale.py models/purchase.py` returns no matches
- [ ] `grep -rn "def recalculate_total" models/sale.py models/purchase.py` returns exactly 2 matches (Sale + Purchase, both kept live)
- [ ] `grep -rn "\.add_item(\|\.remove_item(\|\.update_date(\|\.update_customer(" ui/ services/ tests/ models/` returns no matches (view `add_item` methods excluded)
- [ ] New `tests/test_utils/test_dates.py` exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A test pins one of the deleted model mutators (none found at plan time —
  verify with the grep before deleting).
- A model's `from_db_row` relies on the datetime fallback returning
  `datetime.now()` for a NULL cell (the helper preserves that — verify).
- `utils/dates.py` accidentally imports something from `models/` (it must not —
  keep it dependency-free).

## Maintenance notes

- All model datetime parsing now flows through `utils/dates.py`; a future
  timestamp-format change is a single edit.
- If a future feature needs Sale/Purchase in-memory mutators (e.g. returns/
  refunds design spike), re-add them deliberately with tests — the deleted ones
  were dead drift.
- `models/inventory.py`'s live mutators (`clone`, `set_quantity`,
  `update_quantity`, `create_empty`) are unchanged — do not let a later sweep
  conflate them with the deleted dead pair.