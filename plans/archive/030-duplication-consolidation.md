# Plan 030: Consolidate duplicated code — product_ids, sale-item hydration, receipt text, scan sound

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 3c74057..HEAD -- services/sale_service.py services/purchase_service.py services/mutation_coordinator.py services/purchase_query_service.py ui/sale_view.py ui/purchase_view.py utils/helpers.py utils/ui/sound.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED (refactor of test-covered code; behavior must be identical)
- **Depends on**: plan 029 (run after it — smaller diff surface)
- **Category**: tech-debt
- **Planned at**: commit `3c74057`, 2026-08-16

## Why this matters

Four verified duplication blocks (2026-08-16 audit):

1. `_get_product_ids` — 3 byte-identical copies
   (`sale_service.py:485`, `purchase_service.py:241`,
   `mutation_coordinator.py:50`).
2. Sale-item hydration — 2 near-identical ~24-line blocks in the SAME file
   (`sale_service.py:190-213` in `get_all_sales` and `:590-618` in
   `get_sales_by_date_range`; differ only in comments/indent). A third
   variant in `purchase_query_service._load_items_by_purchase` hydrates
   PURCHASE items — different domain, deliberately left separate.
3. Receipt text builders — `ui/sale_view.py:1246` (`view_sale`) and `:1309`
   (`generate_receipt_preview`) repeat the same header/format block; format
   fixes must be made twice.
4. Scan sound — `ui/sale_view.py:518` uses the `SoundEffect` wrapper
   (`utils/ui/sound.py`, graceful silent fallback); `ui/purchase_view.py:138`
   reimplements it with raw `QSoundEffect` (no fallback).

Every fix to any of these must currently be made N times or drifts silently.
This plan unifies each into one implementation, preserving behavior exactly
(existing tests pin all four surfaces).

## Current state

```python
# utils/ui/sound.py — the wrapper (class name: SoundEffect per sale_view usage;
# read the file for the exact name; sale_view.py:518 does
#   self.scan_sound = SoundEffect("scan.wav")
# and purchase_view.py:138 does
#   self.scan_sound = QSoundEffect()
#   self.scan_sound.setSource(QUrl.fromLocalFile(scan_wav))
#   self.scan_sound.setVolume(0.5)
```

`utils/helpers.py` already exists as the shared-utils home (contains
`create_table` etc.). Existing tests that pin behavior:
- `tests/test_services/test_sale_service.py` — `test_get_all_sales_includes_new_sale`,
  `test_get_sales_by_date_range`, pagination tests (hydration behavior).
- `tests/test_services/test_ux_features.py` — coordinator event tests
  (`finalize_mutation` uses `_get_product_ids`).
- `tests/test_ui/test_sale_view_helpers.py` / `test_sale_view_ux.py` — receipt
  preview/print tests (check which pin receipt text).
- `tests/test_ui/test_purchase_view*` if any — scan sound wiring.

Repo conventions that apply:

- No behavior change; refactor only. Run the suite after each block.
- Spanish user-facing strings (unchanged).
- New public helpers need a caller or a test (AGENTS.md) — all four will have
  callers.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Sale tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_ux_features.py tests/test_services/test_purchase_service.py` | all pass |
| UI tests | `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `utils/helpers.py` — shared `get_product_ids_from_items(items) -> list[int]`
- `services/sale_service.py`, `services/purchase_service.py`,
  `services/mutation_coordinator.py`, `services/update_sale_workflow.py` —
  delegate to the shared helper; delete the 3 copies
- `services/sale_service.py` — one `_hydrate_sale_items(sales, sale_ids)`
  helper used by both `get_all_sales` and `get_sales_by_date_range`
- `ui/sale_view.py` — one receipt-text builder used by `view_sale` and
  `generate_receipt_preview`
- `ui/purchase_view.py` — use the `SoundEffect` wrapper; drop the raw
  `QSoundEffect`/`QUrl` usage and the now-unused QtMultimedia import

**Out of scope** (do NOT touch):
- `services/purchase_query_service.py` — its purchase-item hydration is a
  different domain (purchase vs sale items); documented as intentionally
  separate
- Any behavior change to the receipt OUTPUT (print/preview text must remain
  byte-identical to today's `view_sale` output)
- Any other duplication beyond the four blocks

## Git workflow

- Branch: `advisor/030-duplication-consolidation`
- Commit per block (4 commits); message style follows the repo (`refactor: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Shared `get_product_ids_from_items`

1. Add to `utils/helpers.py` (module-level, with docstring):
   ```python
   def get_product_ids_from_items(items: list[Any]) -> list[int]:
       """Extract unique product ids from sale/purchase items (dicts or objects)."""
       product_ids: list[int] = []
       for item in items:
           product_id = (
               item["product_id"]
               if isinstance(item, dict)
               else getattr(item, "product_id", None)
           )
           if product_id is not None and product_id not in product_ids:
               product_ids.append(int(product_id))
       return product_ids
   ```
2. In `sale_service.py`, `purchase_service.py`, `mutation_coordinator.py`:
   replace each `self._get_product_ids(...)` / `MutationCoordinator._get_product_ids(...)`
   call with `get_product_ids_from_items(...)` (import from `utils.helpers`),
   then DELETE the three `_get_product_ids` definitions.
   Note: `services/update_sale_workflow.py:86` calls
   `self.sale_service._get_product_ids(...)` — switch it to the shared helper too.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py tests/test_services/test_purchase_service.py tests/test_services/test_ux_features.py` → all pass; `rg -n "_get_product_ids" services/` → no matches.

### Step 2: One hydration helper in sale_service

1. Extract the items query + `items_by_sale` grouping from `get_all_sales`
   (lines 190-213) into a private module-level or static helper, e.g.:
   ```python
   @staticmethod
   def _hydrate_sale_items(sales: list[Sale], sale_ids: list[int]) -> None:
       """Batch-load items for the given sales and attach them in place."""
       placeholders = ",".join("?" * len(sale_ids))
       items_query = f""" ...same query as get_all_sales... """  # nosec B608
       items_rows = DatabaseManager.fetch_all(items_query, tuple(sale_ids))
       items_by_sale: dict[int, list[SaleItem]] = {}
       for item_row in items_rows:
           sid = item_row["sale_id"]
           items_by_sale.setdefault(sid, []).append(SaleItem.from_db_row(item_row))
       for sale in sales:
           sale.items = items_by_sale.get(sale.id or 0, [])
   ```
   (Use the exact query text and `# nosec B608` from the current
   `get_all_sales` block.)
2. Call it from both `get_all_sales` (replacing lines 190-213) and
   `get_sales_by_date_range` (replacing lines 590-618). The two call sites
   differ only in which sales rows they pass — keep their surrounding code
   (sales fetch, pagination, logging) untouched.

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py` → all pass (pagination + date-range tests included).

### Step 3: One receipt-text builder in sale_view

1. Read `view_sale` (1246-1308) and `generate_receipt_preview` (1309-1357)
   carefully. Determine the exact differences (likely only the return vs
   print path). Extract the shared header/format text into a single private
   method, e.g. `_build_receipt_text(self, sale: Sale) -> str`, containing
   the FULL receipt text as `view_sale` builds it today.
2. `generate_receipt_preview` becomes `return self._build_receipt_text(sale)`
   (preserving its current output). `view_sale` uses the same builder and
   keeps its print/show behavior.
3. If `view_sale` and the preview text DIFFER today (e.g. preview adds a
   header the print doesn't), preserve `view_sale`'s printed output exactly
   and make the preview a superset ONLY if the existing preview tests pin
   it — otherwise unify to the printed form. When in doubt, preserve
   `view_sale` (the printed receipt) and adjust the preview to match, then
   run the UI tests to confirm.

**Verify**: `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` → all pass (receipt preview/print tests included — check which files pin receipt text: `tests/test_ui/test_sale_view_helpers.py`, `test_sale_view_ux.py`).

### Step 4: purchase_view uses the SoundEffect wrapper

1. Read `utils/ui/sound.py` for the wrapper's exact name and constructor
   (`SoundEffect("scan.wav")` per sale_view). Replace purchase_view's
   `setup_scan_sound` with the wrapper usage mirroring sale_view:
   ```python
   from utils.ui.sound import SoundEffect
   ...
   def setup_scan_sound(self):
       self.scan_sound = SoundEffect("scan.wav")
   ```
   (Drop the raw `QSoundEffect`, `QUrl.fromLocalFile`, `setVolume` and the
   now-unused `PySide6.QtMultimedia` import. If the wrapper supports volume,
   keep 0.5; if not, accept the wrapper default — parity with sale_view is
   the goal.)
2. Verify the scan still plays: `rg -n "scan_sound" ui/purchase_view.py` →
   setup + play sites.

**Verify**: `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` → all pass; `.venv/bin/ruff check ui/purchase_view.py` → clean.

### Step 5: Full verification

**Verify**:
- `.venv/bin/python -m pytest` → all pass (modulo pre-existing worktree UI exceptions)
- `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean
- `rg -n "QSoundEffect|QtMultimedia" ui/` → no matches

## Test plan

Existing tests pin all four surfaces; no new tests required unless a block's
behavior isn't covered (check first):
- product_ids: `test_finalize_mutation_emits_one_inventory_event_per_distinct_product`
  (test_ux_features.py) + sale/purchase audit paths.
- hydration: `get_all_sales`/date-range/pagination tests.
- receipt text: sale_view UI tests.
- sound: no test pins the sound itself (headless); the wiring is verified by
  ruff + import success.

If any surface is uncovered, add ONE focused test (e.g. a
`get_product_ids_from_items` unit test in `tests/test_utils/` — check the
existing utils test layout first).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `rg -n "_get_product_ids" services/` exits 1; `get_product_ids_from_items` defined once in `utils/helpers.py`
- [ ] `rg -c "_hydrate_sale_items" services/sale_service.py` shows one definition + two call sites
- [ ] `rg -n "def _build_receipt_text" ui/sale_view.py` → one definition; `view_sale` and `generate_receipt_preview` both use it
- [ ] `rg -n "QSoundEffect|QtMultimedia" ui/` exits 1
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- A UI test pins receipt text that differs between `view_sale` and the
  preview, and unifying changes printed output (report the diff — do not
  silently change what customers see on paper).
- `utils/ui/sound.py`'s wrapper name differs from the plan's assumption
  (report the actual name).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- The four blocks are now single implementations; future format/behavior
  fixes touch one place each.
- `purchase_query_service`'s hydration remains a separate variant by design
  (purchase domain) — if it ever drifts further, revisit.
- Reviewer scrutiny: byte-identical receipt output (printed receipt is a
  customer-facing artifact), the `# nosec B608` preserved on the moved
  hydration query, and no volume/UX change in the purchase scan sound.
