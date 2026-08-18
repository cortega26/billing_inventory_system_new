# Plan 049: Move receipt-ID generation into ReceiptService

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/sale_service.py services/receipt_service.py tests/test_services/test_receipt_service.py tests/test_ui/test_sale_view_helpers.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S-M
- **Risk**: MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

`SaleService` mixes three responsibilities: sale CRUD, the receipt subsystem
(receipt-ID policy, PDF orchestration), and statistics. `ReceiptService`
already exists and owns PDF rendering (`generate_pdf`), but the receipt-ID
policy (`_build_receipt_id`, `generate_receipt_id`, `_update_sale_receipt_id`)
lives in `SaleService` — so a change to receipt numbering touches the sale CRUD
class and its tests, and `ReceiptService` cannot be reused by any other flow.
This plan moves the receipt-ID policy into `ReceiptService` (SRP) while keeping
`SaleService`'s public receipt methods as thin delegates (the UI at
`ui/sale_view.py:1231,1254` depends on them).

## Current state

- `services/sale_service.py:418-421` — `generate_receipt_id(sale_date)` → `_build_receipt_id`.
- `services/sale_service.py:423-441` — `generate_receipt(sale_id)` — fetches the
  sale, generates the ID if missing, persists it, returns it.
- `services/sale_service.py:443-450` — `_update_sale_receipt_id(sale_id,
  receipt_id)` — `UPDATE sales SET receipt_id = ? WHERE id = ?`, raises
  `NotFoundException` if no row.
- `services/sale_service.py:470-488` — `_build_receipt_id(sale_date_str)` —
  `YYMMDD` prefix + `MAX(CAST(SUBSTR(receipt_id, 7) AS INTEGER))` query; raises
  `ValidationException` past 999/day.
- `services/sale_service.py:452-462` — `save_receipt_as_pdf(sale_id, filepath)` —
  already a thin delegate: fetches sale + items, calls
  `self.receipt_service.generate_pdf(sale, items, filepath)`.
- `services/receipt_service.py:12-17` — `ReceiptService.__init__` is a `pass`
  stub with a comment; `generate_pdf(sale, items, filepath)` renders the PDF.
- Callers: `ui/sale_view.py:1231` `save_receipt_as_pdf`, `:1254`
  `generate_receipt`; `tests/test_services/test_receipt_service.py` uses
  `save_receipt_as_pdf`. `generate_receipt_id` has only internal/test callers.

**Repo conventions**:
- `ReceiptService` may use `DatabaseManager` (it is a service; only `ui/` is
  barred from direct DB access).
- Public method names on `SaleService` that callers use stay stable.
- Behavior-preserving refactor; receipt-ID format and daily-999 cap unchanged.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Receipt tests | `.venv/bin/python -m pytest tests/test_services/test_receipt_service.py` | all pass |
| Sale service tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_update_sale_workflow.py` | all pass |
| Sale UI tests | `.venv/bin/python -m pytest tests/test_ui/test_sale_view_helpers.py tests/test_ui/test_sale_view_ux.py` | all pass (xvfb) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `services/receipt_service.py`
- `services/sale_service.py`
- `tests/test_services/test_receipt_service.py`

**Out of scope**:
- The statistics slice of `SaleService` (`get_total_sales`, `get_total_units_sold`,
  `get_total_profits`, `get_sale_statistics`) — moving those to the analytics
  engine is a separate decision (dashboard KPIs consume them; tracked as
  follow-up)
- The receipt PDF layout/labels (plan 035)
- `ReceiptService.__init__` stub (keep it; harmless)

## Git workflow

- Branch: `advisor/049-receipt-subsystem`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Move the receipt-ID logic into ReceiptService

In `services/receipt_service.py`, add imports (`datetime` from `datetime`,
`DatabaseManager`, `validate_integer`, `validate_string` from validators) and
port these methods from `SaleService` verbatim (rename only if needed for
clarity; keep the logic identical):

- `generate_receipt_id(sale_date: datetime) -> str` → `_build_receipt_id(sale_date.strftime("%Y-%m-%d"))`
- `_build_receipt_id(sale_date_str: str) -> str` (the YYMMDD + MAX(SUBSTR) query + 999 cap)
- `update_sale_receipt_id(sale_id: int, receipt_id: str) -> None` (the UPDATE +
  NotFoundException guard)

**Verify**: `grep -n "def generate_receipt_id\|def _build_receipt_id\|def update_sale_receipt_id" services/receipt_service.py` shows all three.

### Step 2: Make SaleService delegate

In `services/sale_service.py`:
- Delete `_build_receipt_id` (:470-488) and `_update_sale_receipt_id` (:443-450)
  and `generate_receipt_id` (:418-421).
- Rewrite `generate_receipt(sale_id)` (:423-441) to use the ReceiptService:
  ```python
  sale = self._require_sale(sale_id)
  if not sale.receipt_id:
      if sale.date is None:
          raise ValidationException("Sale date is required to generate receipt")
      receipt_id = self.receipt_service.generate_receipt_id(sale.date)
      self.receipt_service.update_sale_receipt_id(sale_id, receipt_id)
      sale.receipt_id = receipt_id
  else:
      receipt_id = sale.receipt_id
  logger.info(...)
  return receipt_id
  ```
- `save_receipt_as_pdf` (:452-462) already delegates — leave as-is.
- Remove now-unused imports (`datetime` is still used elsewhere in the file —
  check; `validate_string` may become unused — check with ruff).

**Verify**: `grep -n "_build_receipt_id\|_update_sale_receipt_id" services/sale_service.py` → no matches.
`.venv/bin/python -m pytest tests/test_services/test_receipt_service.py tests/test_services/test_sale_service.py` → pass.

### Step 3: Remove the __init__ stub comment

In `services/receipt_service.py`, replace the `__init__` body/pass with nothing
special — delete the method entirely if the class needs no constructor (Python
defaults apply), or leave it; prefer deleting it so the class is plain.

**Verify**: `.venv/bin/python -c "from services.receipt_service import ReceiptService; r = ReceiptService(); print(type(r).__name__)"` → `ReceiptService`.

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Existing tests (`test_receipt_service.py`, `test_sale_service.py`) cover the
  behavior; update any that call `SaleService._build_receipt_id` or
  `generate_receipt_id` directly to call `ReceiptService` instead (or through
  the public `generate_receipt`).
- Add one test in `tests/test_services/test_receipt_service.py` that generates
  two receipts for the same date and asserts sequential numbering + the 999/day
  cap raises `ValidationException` (move from any sale-service test that pinned
  `_build_receipt_id`).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -n "_build_receipt_id\|_update_sale_receipt_id\|def generate_receipt_id" services/sale_service.py` returns no matches
- [ ] `grep -rn "def generate_receipt_id\|def _build_receipt_id\|def update_sale_receipt_id" services/receipt_service.py` shows all three
- [ ] Receipt sequencing/cap test exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A test calls `SaleService._build_receipt_id`/`generate_receipt_id` in a way
  that can't be redirected cleanly.
- Removing the `datetime`/`validate_string` imports from `sale_service.py`
  breaks another use in the file (check with ruff; only remove truly unused
  imports).
- The UI's receipt flow (`ui/sale_view.py:1231,1254`) stops working after the
  refactor.

## Maintenance notes

- Receipt-ID policy is now owned by `ReceiptService`; a future receipt/returns
  feature (direction candidate) can reuse it without touching `SaleService`.
- The statistics slice of `SaleService` is the remaining SRP debt — moving it
  to the analytics engine is tracked as follow-up (dashboard KPI callers must
  be re-pointed first).
- Reviewer should verify the daily-receipt-cap error message is unchanged and
  that a second receipt on the same day gets the next sequential number.