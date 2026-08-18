# Plan 047: UpdateSaleWorkflow uses public SaleService methods; drop lazy import

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/update_sale_workflow.py services/sale_service.py`
> If either file changed, compare the "Current state" excerpts against the live
> code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: MED
- **Depends on**: 020 (characterization tests pin this flow — run them)
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

`UpdateSaleWorkflow` calls four underscore-private `SaleService` methods
(`_validate_sale_items`, `_require_sale`, `_update_sale`, `_update_sale_items`).
The underscore signals "internal, don't call me" — but here they ARE the
cross-class update contract, so the naming lies and pyright can't help a
signature change. Additionally, `SaleService.update_sale` imports the workflow
INSIDE the method body (`sale_service.py:344`) even though
`update_sale_workflow.py` imports nothing from `sale_service` — the lazy import
dodges a cycle that doesn't exist and hides the dependency from static
analysis. This plan makes the contract explicit (public names + docstrings) and
moves the import to module level.

## Current state

- `services/sale_service.py:340-346` — `update_sale` body:
  ```python
  def update_sale(self, sale_id, customer_id, date, items):
      from services.update_sale_workflow import UpdateSaleWorkflow
      UpdateSaleWorkflow(self).execute(sale_id, customer_id, date, items)
  ```
- `services/sale_service.py:490-543` — `_validate_sale_items(items)` (called by
  `create_sale` :79 and the workflow), `_insert_sale_items(sale_id, items)`
  (called by `_update_sale_items`).
- `services/sale_service.py:547-563` — `_update_sale(...)` and
  `_update_sale_items(...)` — their ONLY production callers are the workflow
  (`update_sale_workflow.py:65,70`).
- `services/sale_service.py:180-185` — `_require_sale(sale_id)` — called by
  `delete_sale`, `cancel_sale`, `generate_receipt` (same class) and the
  workflow (:39).
- `services/update_sale_workflow.py:16-136` — class holding only `sale_service`;
  calls the four private methods at :36, :39, :65, :70. `_validate_inventory_for_sale_update`
  (:105-136) is real value and stays.
- Tests pinning this flow: `tests/test_services/test_update_sale_workflow.py`
  (plan 020), `tests/test_critical_backend_flows.py`.

**Repo conventions**:
- Public methods with docstrings for cross-class contracts; `_`-private for
  same-class internals.
- Module-level imports; lazy imports only when a real cycle exists.
- High-Risk Area (AGENTS.md) — behavior-preserving refactor only; plan 020's
  characterization tests are the safety net.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Workflow tests | `.venv/bin/python -m pytest tests/test_services/test_update_sale_workflow.py tests/test_services/test_sale_service.py tests/test_critical_backend_flows.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `services/sale_service.py`
- `services/update_sale_workflow.py`
- Tests that reference the private names

**Out of scope**:
- The workflow's orchestration logic (`execute` flow, pre-validation,
  transaction boundaries) — untouched
- `_insert_sale_items` (keep private; internal to SaleService)
- The `sale_view.py` lazy-import pattern elsewhere (none known)

## Git workflow

- Branch: `advisor/047-workflow-contract`
- Commit per logical unit (`refactor: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Make the four contract methods public with docstrings

In `services/sale_service.py`, rename and document (update ALL callers in the
same file):
- `_validate_sale_items` → `validate_sale_items` — add docstring:
  `"""Validate a list of sale item dicts and compute each item's profit in place. Part of the update-sale workflow contract."""`
- `_require_sale` → `require_sale` — add docstring:
  `"""Return the sale with the given ID or raise NotFoundException. Public because the update-sale workflow needs it."""`
  (Keep the existing same-class callers working — they call the new name.)
- `_update_sale` → `update_sale_record` — docstring:
  `"""Persist the updated sale header row. Part of the update-sale workflow contract."""`
- `_update_sale_items` → `replace_sale_items` — docstring:
  `"""Delete and re-insert the sale's items. Part of the update-sale workflow contract."""`

**Verify**: `grep -n "def validate_sale_items\|def require_sale\|def update_sale_record\|def replace_sale_items" services/sale_service.py` shows the four public defs.

### Step 2: Update the workflow's call sites

In `services/update_sale_workflow.py`, replace:
- `self.sale_service._validate_sale_items(items)` (:36) →
  `self.sale_service.validate_sale_items(items)`
- `self.sale_service._require_sale(sale_id)` (:39) → `self.sale_service.require_sale(sale_id)`
- `self.sale_service._update_sale(...)` (:65) → `self.sale_service.update_sale_record(...)`
- `self.sale_service._update_sale_items(...)` (:70) → `self.sale_service.replace_sale_items(...)`

**Verify**: `grep -n "_validate_sale_items\|_require_sale\|_update_sale\b\|_update_sale_items" services/update_sale_workflow.py` → no matches.

### Step 3: Hoist the import to module level

In `services/sale_service.py`:
- Add `from services.update_sale_workflow import UpdateSaleWorkflow` to the top
  imports (alphabetical position among the `services.*` imports).
- Remove the in-method `from services.update_sale_workflow import UpdateSaleWorkflow` (:344).
- Confirm no circular import: `update_sale_workflow.py` imports from
  `database`, `models`, `services.audit_service`, `services.inventory_service`,
  `services.mutation_coordinator`, `utils.*` — NOT `services.sale_service` —
  so a module-level import in sale_service is safe.

**Verify**: `.venv/bin/python -c "import services.sale_service"` → exit 0.
`grep -n "from services.update_sale_workflow" services/sale_service.py` → matches only the top-level import.

### Step 4: Run the workflow + sale + full suites

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_update_sale_workflow.py tests/test_services/test_sale_service.py tests/test_critical_backend_flows.py` → all pass.
`.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .` → exit 0;
`.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- No new tests required (pure rename + import hoist; existing characterization
  tests cover the behavior). If a test referenced the private names, update it.

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn "_validate_sale_items\|_require_sale\|_update_sale\b\|_update_sale_items" services/` returns no matches
- [ ] `grep -n "from services.update_sale_workflow" services/sale_service.py` is the only match (module level)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- Importing `UpdateSaleWorkflow` at module level creates an import cycle
  (pyright or a runtime import fails).
- A test depends on the private names (update it; if a test does something the
  rename breaks structurally, report).
- `require_sale`'s rename breaks a same-class caller you missed (grep before
  renaming).

## Maintenance notes

- The update-sale contract is now four public methods on `SaleService`
  (`validate_sale_items`, `require_sale`, `update_sale_record`,
  `replace_sale_items`) — changing their signatures must keep the workflow and
  its characterization tests in mind.
- The class-vs-functions question for `UpdateSaleWorkflow` (it holds no state)
  is tracked separately; this plan only makes the coupling honest.
- Reviewer should verify a sale edit round-trip through the UI (edit dialog →
  save) still restores/re-applies stock exactly once (plan 020 asserts this).