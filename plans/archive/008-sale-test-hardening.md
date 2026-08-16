# Plan 008: Sale-domain test hardening + purchase-delete reversal + suite cleanup

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
- **Effort**: S-M
- **Risk**: LOW
- **Depends on**: 007 (cache-freshness tests assert the post-007 contract)
- **Category**: tests
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

The sale domain — the app's core mutation flow — has the weakest regression net
of the three ledger entities:

1. **Sale signals are never asserted.** Purchases have signal-capture tests
   (`tests/test_services/test_purchase_service.py:209-277`); customers do
   (`test_customer_service.py:195-257`); `tests/test_services/test_sale_service.py`
   (452 lines) has zero `event_system` assertions. A dropped `sale_added`/
   `sale_deleted` emission (the `MutationCoordinator` contract per AGENTS.md)
   breaks the sales-tab refresh silently.
2. **Purchase-delete inventory reversal is asserted nowhere.** The delete
   test asserts only event payloads — never that inventory was decremented or
   rows removed. AGENTS.md's "reverse and reapply exactly once" is unverified
   for purchases.
3. **Suite pollution**: a stale skip test references nonexistent `void_sale`
   (`tests/test_services/test_sale_service.py:132-149`), and
   `tests/test_services/test_ux_features.py:18-107` `test_manual` is a
   print-test that re-initializes the shared DB mid-suite and loads
   `schema.sql` (the one test environment that diverges from the `db_manager`
   fixture).
4. **Dead test artifacts**: `tests/requirements-test.txt` is tracked and
   unreferenced (stale `pytest>=7.0.0` pins); `tests/utils/base_test.py:39-41`
   has an unreachable duplicate `return self.mock_db`.

## Current state

- `tests/test_services/test_purchase_service.py:259-277`:
  ```python
  def test_delete_purchase_emits_purchase_deleted_and_inventory_events_once(self, ...):
      purchase_id = purchase_service.create_purchase(**sample_purchase_data)
      ...
      purchase_service.delete_purchase(purchase_id)
      assert purchase_payloads == [purchase_id]
      assert inventory_payloads == [sample_product.id]
      # <-- no inventory quantity assertion, no row-existence assertion
  ```
- `tests/test_services/test_sale_service.py:132-149` — `@pytest.mark.skip(reason="Void sale functionality not fully implemented")` on `test_void_sale` calling `sale_service.void_sale` (which does not exist; the real flow is `cancel_sale`, fully tested).
- `tests/test_services/test_ux_features.py:18-107` — module-level `test_manual` (prints, `DatabaseManager.initialize(":memory:")`, loads `schema.sql` via `conn.executescript`).
- `tests/utils/base_test.py:39-41` — `return self.mock_db` twice (second unreachable).
- `services/mutation_coordinator.py:12-47` — the finalization contract (cache clears + signals).
- `services/sale_service.py:116-121` — `sale_added` emission; `:290-295` — `sale_deleted`; `:336-341` — `sale_updated` (via cancel); `services/update_sale_workflow.py:97-102` — `sale_updated` (edit path).
- `services/purchase_service.py:107-131` — `delete_purchase` (inventory `multiplier=-1.0` at `:112-115`).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Sale + purchase tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py -q` | all pass |
| UX features tests | `.venv/bin/python -m pytest tests/test_services/test_ux_features.py -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `tests/test_services/test_sale_service.py` — signal-capture tests
- `tests/test_services/test_purchase_service.py` — delete-reversal assertions
- `tests/test_services/test_ux_features.py` — remove `test_manual`
- `tests/utils/base_test.py` — remove duplicate return
- `tests/requirements-test.txt` — DELETE (tracked file, zero references)
- `tests/conftest.py` — only if the signal-capture helper needs a shared fixture (check `tests/utils/test_helpers.py` for `capture_signal` first — it exists per test_purchase_service.py usage)

**Out of scope**:
- `services/*` — NO production code changes in this plan (if a test uncovers a
  real bug, write the failing test, then STOP and report — do not fix silently)
- Plan 001's cancelled-sale tests (they land in that plan)
- Analytics/inventory/receipt test gaps (plans 009, 010)

## Git workflow

- Branch: `advisor/008-sale-test-hardening`
- Commit messages: `test: capture sale-domain signals`, `test: assert purchase-delete inventory reversal`, `test: remove stale void_sale skip and test_manual print-test`
- Do NOT push unless instructed.

## Steps

### Step 1: Sale signal capture tests

In `tests/test_services/test_sale_service.py`, add signal-capture tests
mirroring `tests/test_services/test_purchase_service.py:209-277` exactly
(import `capture_signal` from `tests.utils.test_helpers` — check its path and
the purchase test's import line first):

1. `test_create_sale_emits_sale_added_and_inventory_events` — create → assert
   `sale_added` payload `[sale_id]` and `inventory_changed` payloads contain each
   distinct product id once.
2. `test_delete_sale_emits_sale_deleted_and_inventory_events` — create, delete →
   `sale_deleted` `[sale_id]`, inventory restored.
3. `test_cancel_sale_emits_sale_updated` — create, cancel → `sale_updated`
   `[sale_id]`.
4. If the edit path (`update_sale` public entry through the workflow) emits
   `sale_updated` too, add `test_update_sale_emits_sale_updated_once`.

Use the `db_manager` fixture and the existing `sample_sale_data`/`sample_product`
fixtures in that file.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py -q` → all pass, including the new tests.

### Step 2: Purchase-delete reversal assertions

Extend `test_delete_purchase_emits_purchase_deleted_and_inventory_events_once`
(`tests/test_services/test_purchase_service.py:259-277`) with:

- After delete: `inventory_service.get_inventory(sample_product.id).quantity == 0`
  (the sample purchase data buys 10 units; check the fixture's quantity and
  assert the exact post-delete value).
- `DatabaseManager.fetch_one("SELECT 1 FROM purchase_items WHERE purchase_id = ?", (purchase_id,)) is None`
- `DatabaseManager.fetch_one("SELECT 1 FROM purchases WHERE id = ?", (purchase_id,)) is None`

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_purchase_service.py -q` → all pass.

### Step 3: Remove suite pollution

- Delete the skipped `test_void_sale` (`tests/test_services/test_sale_service.py:132-149`).
- Delete `test_manual` and its `if __name__ == "__main__"` block
  (`tests/test_services/test_ux_features.py:18-107` and the trailing main
  block — check the whole file; keep `TestUXFeatures` intact).
- Delete `tests/requirements-test.txt` (confirm zero references first:
  `grep -rn "requirements-test" --include="*.py" --include="*.md" --include="*.yml" . --exclude-dir=.venv --exclude-dir=.git`).
- Remove the duplicate `return self.mock_db` in `tests/utils/base_test.py:39-41`.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_ux_features.py tests/test_services/test_sale_service.py -q` → all pass; `grep -rn "void_sale" tests/` → no matches; `git status` shows `tests/requirements-test.txt` deleted.

### Step 4: Cache-freshness assertions (post-007)

If plan 007 has landed, add the three cache-freshness tests described in
007/Step 4 here (sale list, product list, product details). If 007 has NOT
landed, skip this step and note it in the report (the tests would fail against
the pre-007 behavior).

**Verify**: `.venv/bin/python -m pytest tests/test_services -q` → all pass.

## Test plan

- New: 3-4 sale signal tests (Step 1), purchase-delete reversal (Step 2),
  optional cache freshness (Step 4).
- Removed: stale skip, print-test, dead manifest, duplicate return.
- Pattern exemplars: `test_purchase_service.py:209-277` (capture_signal),
  `test_critical_backend_flows.py:60-80` (sale create/delete inventory math).

## Done criteria

- [ ] `.venv/bin/python -m pytest tests/test_services tests/test_critical_backend_flows.py -q` exits 0
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `grep -rn "void_sale" tests/` → no matches
- [ ] `grep -rn "requirements-test" . --exclude-dir=.venv --exclude-dir=.git` → no matches
- [ ] `git status` shows `tests/requirements-test.txt` deleted and `tests/run_tests.py` NOT touched
- [ ] New sale signal tests exist (grep `capture_signal` in `test_sale_service.py` → matches)
- [ ] Purchase-delete test asserts inventory quantity and row deletion
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] No files outside the in-scope list are modified (production code untouched)
- [ ] `plans/README.md` status row updated

## STOP conditions

- A new signal test reveals a MISSING or DOUBLE emission in production code —
  write the failing test, then STOP and report (the fix belongs in a plan like
  001/007 territory, not silently here).
- `capture_signal` lives somewhere other than `tests/utils/test_helpers.py` —
  locate it from the purchase test's imports; do not reimplement it.
- Deleting `test_manual` removes coverage that a real test elsewhere relies on
  (check for cross-references first) — STOP and report.

## Maintenance notes

- Plan 011's dead-code sweep will flag `sale_service.void_sale` references in
  tests — this plan removes them first, so run 011 after 008.
- The purchase-delete assertions double as the safety net for any future
  `delete_purchase` refactor.
- Reviewer: confirm production code diffs are ZERO in this plan's PR.
