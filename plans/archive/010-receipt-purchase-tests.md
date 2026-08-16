# Plan 010: Receipt + purchase_query characterization tests

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
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

Two modules split out in recent refactors have zero test references, so their
behavior is unpinned:

1. **ReceiptService is completely untested.** `services/receipt_service.py` has
   `generate_pdf` (`:17`) and `send_via_whatsapp` (`:87`, a logging placeholder).
   The receipt-id sequencing that depends on it —
   `SaleService._build_receipt_id` (`services/sale_service.py:463-481`:
   `MAX(CAST(SUBSTR(receipt_id,7) AS INTEGER))+1`, daily `>999` limit) — is also
   untested. Receipts are the billing artifact the store hands customers; a
   regression in id sequencing (duplicate ids fail on the UNIQUE constraint) or
   PDF generation ships silently.
2. **PurchaseQueryService split methods are untested.** `get_purchase_trends`
   (`services/purchase_query_service.py:98-112`, TimeInterval validation) and
   `get_purchases_by_supplier` (`:67`) have zero references in tests.

These are "characterization tests first" targets: pin current behavior before
any future refactor (e.g., plan 011's dead-code sweep, or a purchase workflow
change).

## Current state

- `services/receipt_service.py:17` — `generate_pdf(self, sale, items, filepath)` uses reportlab `canvas` (`:29`); `:87-98` — `send_via_whatsapp` validates and logs only.
- `services/sale_service.py:463-481` — `_build_receipt_id(sale_date_str)`: date-part `%y%m%d`, `MAX(CAST(SUBSTR(receipt_id, 7) AS INTEGER))`, `next_number > 999` → `ValidationException`, returns `f"{date_part}{next_number:03d}"`.
- `services/sale_service.py:408-426` — `generate_receipt` public path.
- `services/purchase_query_service.py:98-112` — `get_purchase_trends(start_date, end_date, interval="month")`; `TimeInterval` from `models/enums.py`; invalid interval → `ValidationException`.
- `services/purchase_query_service.py:67`-ish — `get_purchases_by_supplier`.
- Existing test patterns: `tests/test_services/test_purchase_service.py` (service tests with `db_manager`), `tests/test_utils/` (pure helper tests).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| New tests | `.venv/bin/python -m pytest tests/test_services/test_receipt_service.py tests/test_services/test_purchase_query_service.py tests/test_services/test_sale_service.py -q` | all pass (files 1-2 are new) |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope** (create the first two):
- `tests/test_services/test_receipt_service.py` (NEW)
- `tests/test_services/test_purchase_query_service.py` (NEW)
- `tests/test_services/test_sale_service.py` — add `_build_receipt_id` tests here (it is private to SaleService)

**Out of scope**:
- `services/receipt_service.py`, `services/purchase_query_service.py`, `services/sale_service.py` — NO production changes. If a test exposes a bug (e.g., receipt-id sequence collision), write the failing test and STOP/report.
- WhatsApp transport mocking of a real API — `send_via_whatsapp` is a placeholder; assert it validates and logs, nothing more (pin current behavior).

## Git workflow

- Branch: `advisor/010-receipt-purchase-tests`
- Commit messages: `test: characterize receipt generation and id sequencing`, `test: characterize purchase query split methods`
- Do NOT push unless instructed.

## Steps

### Step 1: Receipt-id sequencing tests

In `tests/test_services/test_sale_service.py`, add tests for the private
`_build_receipt_id` (call it as `SaleService._build_receipt_id(date_str)`):

1. First receipt of the day → `yyMMdd001`.
2. Seed a sale with `receipt_id = "260815042"` directly via
   `DatabaseManager.execute_query("INSERT INTO sales (date, receipt_id, ...) VALUES (...)")`
   (match the sales table's required columns — check `schema.sql` sales DDL) →
   `_build_receipt_id("2026-08-15")` returns `260815043`.
3. Seed `receipt_id = "260815999"` → raises `ValidationException` (daily limit).
4. A sale from a DIFFERENT day does not affect the count (seed `260814005`,
   call for 08-15 → `260815001`).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py -q` → all pass.

### Step 2: PDF generation smoke test

In `tests/test_services/test_receipt_service.py`:

1. Seed a product + sale via the `db_manager` fixture (mirror the seeding in
   `tests/test_critical_backend_flows.py` or `tests/test_services/test_sale_service.py`).
2. `sale_service.save_receipt_as_pdf(sale_id, str(tmp_path / "receipt.pdf"))`
   (fixture `tmp_path` is built in; this writes outside the repo — allowed).
3. Assert the file exists, non-empty, and starts with `%PDF` bytes.
4. `send_via_whatsapp` characterization: call
   `sale_service.send_receipt_via_whatsapp(sale_id, "912345678")` → returns
   None, no exception (it only logs today); assert a valid phone format rejects
   (`validate_string` with max_length=20 — test an over-length value raises).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_receipt_service.py -q` → all pass.

### Step 3: Purchase query characterization

In `tests/test_services/test_purchase_query_service.py`:

1. Seed 2-3 purchases (different dates/suppliers) via `PurchaseService.create_purchase` with the `db_manager` fixture (reuse `tests/test_services/test_purchase_service.py`'s `sample_purchase_data`-style fixture or build inline).
2. `get_purchase_trends("2026-08-01", "2026-08-31", "day")` → returns per-day buckets matching the seeded totals.
3. `get_purchase_trends(..., interval="bogus")` → `ValidationException`.
4. `get_purchase_trends` with an empty range → empty list (pin the shape).
5. `get_purchases_by_supplier("Proveedor A")` → returns that supplier's purchases only.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_purchase_query_service.py -q` → all pass.

## Test plan

- Receipt id: 4 cases (first-of-day, increment, 999 limit, cross-day isolation).
- PDF: file exists / non-empty / `%PDF` magic; WhatsApp placeholder behavior.
- Purchase trends: happy, invalid interval, empty range; supplier filter.
- Patterns: `test_critical_backend_flows.py` (seeding), `test_purchase_service.py` (service fixture usage).

## Done criteria

- [ ] All three test files pass (2 new files + additions to `test_sale_service.py`)
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] `grep -rn "get_purchase_trends\|get_purchases_by_supplier" tests/` → matches in the new file
- [ ] `grep -rn "_build_receipt_id" tests/` → matches
- [ ] No production files modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

- `_build_receipt_id`'s `> 999` limit is untriggerable in tests because of the
  `MAX(...)` query semantics (e.g., the seeded `999` value collides with the
  implicit unique index) — report the actual behavior; do not weaken the test.
- `save_receipt_as_pdf` requires `sale.date` or other fields the seed does not
  provide (the `if sale.date is None` guard at `sale_service.py:415`) — seed a
  real date; only STOP if the PDF path raises for an unexpected reason.
- A test exposes a real bug in any of the three modules — write the failing
  test, STOP, and report. Do not fix production code in this plan.

## Maintenance notes

- Plan 011's dead-code sweep must NOT delete `send_receipt_via_whatsapp`/
  `get_product_details` if this plan's tests reference them — check plan 011's
  zero-reference guard runs AFTER these tests land (it does per plans/README.md
  dependency notes).
- When WhatsApp is ever implemented for real (direction candidate 2), the
  placeholder characterization test must be updated, not just extended.
- Reviewer: confirm the PDF test writes only to `tmp_path`.
