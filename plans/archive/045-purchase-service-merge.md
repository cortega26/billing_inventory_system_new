# Plan 045: Merge PurchaseQueryService into PurchaseService

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/purchase_service.py services/purchase_query_service.py tests/test_services/test_purchase_service.py tests/test_services/test_purchase_query_service.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: none (run before any purchase-flow refactor)
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

`PurchaseService` is a 10-method pass-through facade: every read delegates to
`PurchaseQueryService` (e.g. `purchase_service.py:86-103,141-143,285-319`),
which has NO other consumer — `grep` shows only `purchase_service.py` and tests
import it. The UI uses exactly three of the read methods (`get_all_purchases`,
`get_purchase`, `get_purchase_items`). Every purchase-query change (signature,
cache) must be edited in two files in lockstep, and the read/write split is
fragmentation, not separation: same connection, same `DatabaseManager`, no
read-only enforcement (unlike the analytics engine). `SaleService` keeps its
reads inline — the repo's convergent pattern. This plan merges the query
service into `PurchaseService` (mirroring `SaleService`) and deletes the
facade layer. The read methods that only tests exercise are KEPT (they have
legitimate coverage; deleting them is a separate decision).

## Current state

- `services/purchase_query_service.py` (277 lines) — `get_purchase`,
  `get_all_purchases`, `get_purchase_items`, `get_suppliers`,
  `get_purchases_by_supplier`, `get_purchase_trends`, `get_top_suppliers`,
  `get_supplier_purchases`, `get_purchase_statistics`, `get_purchase_history`,
  `clear_cache` (:240), `_hydrate_purchases` (:246), `_load_items_by_purchase` (:259).
  Uses `@lru_cache(maxsize=1)` on `get_all_purchases` and `get_suppliers`.
- `services/purchase_service.py` — `create_purchase`, `delete_purchase`,
  `update_purchase`, `_insert_purchase`, `_insert_purchase_items`,
  `_validate_purchase_items`, `clear_cache`, plus the 10 delegators:
  `get_purchase` (:86), `get_all_purchases` (:98), `get_purchase_items` (:102),
  `get_suppliers` (:142), `get_purchases_by_supplier` (:286),
  `get_purchase_trends` (:294), `get_top_suppliers` (:300),
  `get_supplier_purchases` (:308), `get_purchase_statistics` (:314),
  `get_purchase_history` (:318). It imports `PurchaseQueryService` at :11.
- UI callers (`ui/purchase_view.py`): `:447` `get_all_purchases()`, `:530` and
  `:634` `get_purchase(id)`, `:550` `get_purchase_items(id)`.
- Tests: `tests/test_services/test_purchase_service.py` and
  `tests/test_services/test_purchase_query_service.py` import
  `PurchaseQueryService` and call its methods directly.
- `PurchaseService.clear_cache` (:321-324) — verify its current body; it likely
  delegates to `PurchaseQueryService.clear_cache` or clears the cached methods.

**Repo conventions**:
- `SaleService` is the exemplar: reads and writes in one class
  (`services/sale_service.py`), batching helpers as module functions or
  private static methods.
- Cache clearing must reach every `@lru_cache` read (AGENTS.md cache contract).
- No dead code: every public method must have a caller or a test (the merged
  methods keep their tests).

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Purchase tests | `.venv/bin/python -m pytest tests/test_services/test_purchase_service.py tests/test_services/test_purchase_query_service.py` | all pass (after update) |
| Purchase UI tests | `.venv/bin/python -m pytest tests/test_ui/ -k purchase` | all pass (xvfb) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `services/purchase_query_service.py` (delete)
- `services/purchase_service.py`
- `tests/test_services/test_purchase_service.py`
- `tests/test_services/test_purchase_query_service.py`

**Out of scope**:
- Deleting the read methods that only tests use (kept — they have coverage)
- Any purchase write-flow behavior (create/delete/update)
- `ui/purchase_view.py` (its call sites are unchanged)

## Git workflow

- Branch: `advisor/045-purchase-service-merge`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Move the query methods into PurchaseService

In `services/purchase_service.py`:
- Remove the `from services.purchase_query_service import PurchaseQueryService`
  import.
- Add the imports the query methods need (`lru_cache`, `PurchaseItem`,
  `TimeInterval`, `validate_date`, `validate_integer`, `validate_string` — merge
  with existing imports; remove any that become unused).
- Paste the bodies of all query methods + `_hydrate_purchases` +
  `_load_items_by_purchase` from `purchase_query_service.py` into
  `PurchaseService` as `@staticmethod`s, converting internal
  `PurchaseQueryService.X` references to `PurchaseService.X`.
- Keep the `@lru_cache` decorators and `@db_operation`/`@handle_exceptions`
  stacking exactly as they are.
- Delete the 10 one-line delegators (their bodies are now the real methods).

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_purchase_query_service.py` — update its imports to `PurchaseService` (or port the tests into `test_purchase_service.py`). `.venv/bin/python -m pytest tests/test_services/test_purchase_service.py` → pass.

### Step 2: Unify cache clearing

Ensure `PurchaseService.clear_cache` clears `PurchaseService.get_all_purchases`
and `PurchaseService.get_suppliers` (both `lru_cache(maxsize=1)`). If the old
`clear_cache` delegated to `PurchaseQueryService.clear_cache`, replace the body
with explicit `cache_clear()` calls on the moved methods.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_purchase_service.py tests/test_services/test_purchase_query_service.py` → pass.

### Step 3: Delete the query-service module

Delete `services/purchase_query_service.py` after confirming nothing imports it.

**Verify**: `grep -rn "PurchaseQueryService\|purchase_query_service" --include="*.py" .`
→ no matches (excluding this plan file).

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Port `tests/test_services/test_purchase_query_service.py` to use
  `PurchaseService` (rename the class references; the test bodies stay
  identical — they assert query behavior, not the class name).
- Keep every read-method test — the merged methods keep their coverage.
- No new behavior tests needed (pure merge).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "PurchaseQueryService\|purchase_query_service" --include="*.py" .` returns no matches (file deleted)
- [ ] `services/purchase_query_service.py` no longer exists (`ls services/`)
- [ ] `grep -n "def get_purchase\b\|def get_all_purchases\|def get_suppliers\|def get_purchase_statistics" services/purchase_service.py` shows real method bodies (not one-liners)
- [ ] `PurchaseService.clear_cache` clears both `lru_cache` reads
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A production caller of `PurchaseQueryService` exists that grep missed.
- `clear_cache` fails to reach a cached method (cache-freshness tests from the
  plan-007 protocol will catch this — run them).
- The `@lru_cache(maxsize=1)` on `get_all_purchases` breaks under the merge
  (it should not — same staticmethod shape as before).

## Maintenance notes

- Purchases now mirror `SaleService`: one service class owns reads + writes.
- The read methods with test-only coverage (`get_suppliers`,
  `get_purchase_statistics`, etc.) are retained for now; if the maintainer
  later decides they'll never be surfaced in a UI, they can be deleted under
  the plan-011 zero-reference guard.
- The audit's separate backlog item "get_all_purchases — zero tests, no
  pagination, lru_cache(maxsize=1)" is NOT addressed here; it is a design
  decision for later.
- Reviewer should verify the cache-freshness contract: creating/updating/
  deleting a purchase still clears `get_all_purchases` (the plan-007 tests
  pin this).