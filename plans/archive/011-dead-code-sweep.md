# Plan 011: Dead code sweep with zero-reference guard

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
- **Depends on**: 008, 009, 010 (their new tests pin behavior and add
  references; run this sweep AFTER them)
- **Category**: tech-debt
- **Planned at**: commit `7453aee`, 2026-08-15

## Why this matters

The codebase ships ~600 lines of dead code that shapes what readers (human or
agent) think is load-bearing:

- 10 zero-caller public methods on `SaleService` (`calculate_total_amount`,
  `calculate_total_profit`, `get_total_sales_by_customer`,
  `get_daily_sales_report`, `get_sales_by_product`,
  `get_sales_distribution_by_category`, `get_top_selling_products`,
  `get_product_details`, `send_receipt_via_whatsapp`, `update_sale_receipt`,
  `get_customer_sales`) — grep-verified zero non-test callers.
- **The "top products" metric exists in 3 divergent copies**: `sale_service.get_top_selling_products`,
  `services/analytics_service.py:323` (live re-implementation), and
  `TopProductsMetric` in `services/analytics/metrics.py:83` — the metric class
  is the winner (services/analytics/ is the read-only contract owner).
- Dead modules: `utils/validation/data_validator.py` (imports `database`
  directly, "deferred import to avoid circular dependency"),
  `utils/validation/mixins.py`, `utils/data_handling/excel_exporter.py`
  (zero importers including tests), `file_extractor.py` (912-line tkinter GUI,
  gitignored-but-tracked), `search.py` (legacy dev script).
- 7 of 13 decorators in `utils/decorators.py` have zero usages
  (`validate_input`, `require_authorization`, `handle_concurrency`,
  `enforce_business_logic`, `retry`, `measure_performance`, `cache_result`);
  the generic predicate API in `utils/validation/validators.py:11-67`
  (`validate`, `validate_and_sanitize`, `is_*`, `matches_pattern`) exists only
  to serve the dead `validate_input` decorator.
- 5 of 9 `utils/sanitizers.py` functions unused (`strip_tags`,
  `sanitize_number`, `sanitize_email`, `sanitize_phone`, `sanitize_url`);
  `truncate_string` duplicates `utils/helpers.py:156`.

This plan deletes verified-dead code with a scripted zero-reference guard, so
the deletion is provably safe, and adds a repo-hygiene rule for the legacy
scripts.

## Current state

- `services/sale_service.py:801,810,605,686,721,757,574,796,454,438,160` —
  the zero-caller methods (verify each with grep before deleting).
- `services/analytics_service.py:320-331` — `clear_cache` (keep); `:323` —
  the live top-products query (keep; delete the sale_service copy only).
- `services/analytics/metrics.py:83` — `TopProductsMetric` (keep).
- `utils/decorators.py:13` helpers — 7 unused (see list above).
- `utils/validation/validators.py:11-67` — generic predicate API.
- `utils/sanitizers.py` — 5 unused functions.
- `utils/helpers.py:156` — `truncate_string` (keep this one).
- `file_extractor.py`, `search.py` — tracked, gitignored, zero importers.
- `tests/test_services/test_sale_service.py:220`-ish — a test referencing
  `get_sale_statistics` (verify which dead methods have test references; those
  tests get deleted in the same change).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Reference check | `grep -rn "<symbol>" --include="*.py" . --exclude-dir=.venv --exclude-dir=.git --exclude-dir=__pycache__` | definition + zero other hits (before delete) |
| Tests | `.venv/bin/python -m pytest tests/test_services tests/test_utils tests/test_validation -q` | all pass |
| Full suite | `.venv/bin/python -m pytest -q` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .` / `.venv/bin/black --check .` / `.venv/bin/pyright` | clean / clean / 0 errors |

## Scope

**In scope**:
- `services/sale_service.py` — the listed zero-caller methods (only those that
  pass the guard; `get_top_selling_products` and `get_sale_statistics` are
  referenced by tests/analytics — see Step 1 handling)
- `utils/decorators.py`, `utils/validation/validators.py` (dead predicate API only),
  `utils/sanitizers.py` (5 functions), `utils/data_handling/excel_exporter.py`,
  `utils/validation/data_validator.py`, `utils/validation/mixins.py` — delete
  the files entirely where the whole file is dead
- `file_extractor.py`, `search.py` — `git rm --cached` (keep on disk? NO —
  delete from the repo; they are legacy dev tools with no importer. If the
  owner objects they are in git history)
- `.gitignore` — remove the `file_extractor.py`/`search.py` lines that exist
  only for these two files (keep `*.log` etc.)
- Tests referencing deleted symbols — delete or update in the same change

**Out of scope**:
- `services/analytics_service.py` and `services/analytics/metrics.py` — KEEP
  the live metric implementations (they are the contract)
- `utils/helpers.py` — keep `truncate_string` here (plan 013/014 territory for
  the junk-drawer split; not this plan)
- `utils/system/logger.py`, `utils/system/event_system.py` — keep
- `file_extractor.py`/`search.py` HISTORY — no history rewriting (same rule as
  plan 003)

## Git workflow

- Branch: `advisor/011-dead-code`
- Commit messages: `refactor: remove dead sale-service methods`, `refactor: delete dead utility modules`, `chore: remove tracked legacy scripts from index`
- Do NOT push unless instructed.

## Steps

### Step 1: Inventory the dead symbols (characterization)

For each candidate symbol, run the reference grep. Classify:

- **Delete**: definition + zero other hits.
- **Test-only references**: the symbol is used by tests but no production code —
  delete symbol AND its tests (verify the tests are pure unit tests of the dead
  code, not coverage of behavior used elsewhere).
- **Live references**: do NOT delete — and record it in the report (this means
  the audit's grep missed a caller; also check `services/analytics_service.py`
  and the UI).

Record the full table in your report (symbol → classification → evidence).

**Verify**: no classification is guessed; every "delete" has its grep output saved.

### Step 2: Delete the safe set

Delete the classified-dead methods, functions, and modules. For whole dead
modules, delete the file and its `__init__`-level re-exports if any (check
`utils/validation/__init__.py` and `utils/data_handling/__init__.py` for
imports of the deleted modules; remove those lines too).

Delete the tests that only exercised deleted code (Step 1 test-only class).

**Verify**: `.venv/bin/python -m pytest tests/test_services tests/test_utils tests/test_validation -q` → all pass. `ruff check .` clean.

### Step 3: Untrack the legacy scripts

`git rm file_extractor.py search.py` (files are gitignored but tracked; this
removes them from the index and disk). Remove their `file_extractor.py` /
`search.py` lines from `.gitignore` only if nothing else needs them (they are
specific filenames — safe to remove). Keep the drift-check and pre-commit
exclude entries for them if the files vanish (`.pre-commit-config.yaml` exclude
becomes harmless dead config — remove it too).

**Verify**: `git status` shows both files deleted; `.venv/bin/python -m pytest -q` still passes.

### Step 4: Add the hygiene rule

Add one paragraph to `AGENTS.md` (under Forbidden Shortcuts or a new short
section): "Do not re-add dead code: any new public method must have a caller or
a test. Deleting code requires the zero-reference grep from plan 011's Step 1."

**Verify**: `grep -n "zero-reference" AGENTS.md` → match.

## Test plan

- No new tests (deletion only). The suite is the regression gate; the
  Step 1 guard is the correctness argument.

## Done criteria

- [ ] Every deleted symbol's Step 1 grep is saved in the report (definition + zero other hits)
- [ ] `.venv/bin/python -m pytest -q` exits 0
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` all clean
- [ ] `git status` shows `file_extractor.py` and `search.py` deleted
- [ ] `grep -rn "get_daily_sales_report\|calculate_total_amount" services/` → no matches
- [ ] `utils/validation/data_validator.py`, `utils/validation/mixins.py`, `utils/data_handling/excel_exporter.py` no longer exist
- [ ] `services/analytics/metrics.py::TopProductsMetric` and `analytics_service.py:323` still exist (the live copies)
- [ ] No live symbols were deleted (spot-check 3 report classifications)
- [ ] `plans/README.md` status row updated

## STOP conditions

- A "delete" candidate has a live production caller you find during Step 1 —
  do not delete; record it and continue with the rest.
- A test in the "delete with symbol" class is actually a behavioral test of
  code that stays (e.g., it exercises the deleted method as part of a flow) —
  STOP and report; do not delete coverage.
- Deleting a whole module breaks imports in a file outside the in-scope list —
  STOP and report (the audit's importer list was wrong).

## Maintenance notes

- The three-copies-of-top-products problem is resolved by deletion here; future
  metric work lives in `services/analytics/metrics.py` only.
- `utils/decorators.py` shrinks to the 6 used helpers; the remaining ones are
  referenced by services/UI (verify at the end that 6 remain).
- Reviewer: the PR should be almost purely deletions — anything else is a red
  flag.
