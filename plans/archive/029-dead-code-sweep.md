# Plan 029: Dead-code sweep — delete 33 fully-dead symbols (zero-reference guard)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 3c74057..HEAD -- models/ database/ services/ utils/ ui/product_view.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S-M
- **Risk**: LOW (all 33 have zero references repo-wide — verified by occurrence-count scan)
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `3c74057`, 2026-08-16

## Why this matters

A focused audit (2026-08-16) found 33 public methods/classes with exactly ONE
occurrence in the entire repo (their own definition) and zero references in
tests. They are dead weight: they invite "fix it in all N places" edits,
inflate the pyright/bandit surface, and some (the model mutation API) imply
an architecture that doesn't exist (mutations live in SQL via services).
This sweep follows plan 011's established protocol: for each symbol,
definition + zero other hits repo-wide (tests included — all 33 are fully
dead, so no test-only classification is needed).

15 additional test-only symbols (e.g. `get_inventory_movements`,
`get_sales_summary`) are deliberately KEPT — they satisfy AGENTS.md's
"caller or test" rule and several are documented tools.

## The 33 symbols (file : method)

**models/**:
- `models/purchase.py`: `add_items`, `get_item_count`, `get_total_quantity`,
  `update_supplier`, `verify_totals`
- `models/customer.py`: `update_identifier_9`, `update_name`
- `models/sale.py`: `update_receipt_id`
- `models/business.py`: `from_dict`

**database/**:
- `database/database_manager.py`: `get_session`

**services/**:
- `services/backup_service.py`: `stop_scheduler`
- `services/category_service.py`: `get_category_statistics`,
  `get_products_in_category`
- `services/inventory_service.py`: `delete_inventory`
- `services/product_service.py`: `get_product_profit_margin`
- `services/receipt_service.py`: `send_via_whatsapp`
- `services/analytics_service.py`: `get_date_range`
- `utils/decorators.py`: `handle_external_service`

**utils/**:
- `utils/helpers.py`: `format_date`, `validate_integer_input`
- `utils/sanitizers.py`: `sanitize_filename`
- `utils/system/logger.py`: `log_method`
- `utils/system/event_system.py`: `disconnect_from_event`, `get_available_events`
- `utils/validation/validators.py`: `validate_boolean`, `validate_email`,
  `validate_int_non_negative`, `validate_phone`, `validate_price_pair`,
  `validate_url`

**ui/**:
- `ui/product_view.py`: `export_products`, `import_products`

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Zero-ref guard (per symbol) | `rg -rn "\b<name>\b" --glob '!*.pyc' .` | only the definition line (pre-deletion) / nothing (post) |
| Lint (catches orphaned imports) | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |
| Full suite | `.venv/bin/python -m pytest` | all pass |

## Scope

**In scope**: the 15 files listed above — method deletions + cleanup of
imports that become unused (ruff F401) as a consequence.

**Out of scope** (do NOT touch):
- The 15 test-only symbols (`config.reset_to_defaults`,
  `analytics_service.get_sales_summary`, `audit_service.get_entries`,
  `category_service.get_category`, `customer_service.get_customer_purchase_history`,
  `inventory_service.get_inventory_movements/get_inventory_turnover`,
  `sale_service.get_sale_statistics/get_sales_by_date_range`,
  `financial_calculator.calculate_sale_totals/round_quantity`,
  `event_system.clear_all_connections`, `logger.clear_logs/rotate_logs`,
  `validators.validate_dict/validate_list`) — they have tests; keep them.
- Internal model validators (`sale.validate_status`, `validate_total_amount`,
  `normalize_quantity`, etc.) — they are CALLED by `post_init_validation`
  (2+ occurrences); not part of this sweep.
- `main_window.import_data`/`export_data` (no-op stubs with menu entries) —
  referenced by the menu; a product decision (remove-or-implement), not dead code.
- Any behavior change beyond deletion (no refactors, no renames).

## Git workflow

- Branch: `advisor/029-dead-code-sweep`
- Commit per step or per logical group; message style follows the repo (`fix: remove dead code: ...` or similar; plan 011 used a single sweep commit)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Delete, group by file, with the guard

For each of the 15 files, delete the listed methods. Work file-by-file; after
each file, run `.venv/bin/ruff check <file>` to surface now-unused imports
(F401) and remove them (e.g. `receipt_service.py` may orphan
`validate_string`; `database_manager.py` may orphan SQLAlchemy `sessionmaker`
imports if `get_session` was their only use — check; `event_system.py` may
orphan nothing). Do NOT remove imports that other code still uses.

Per-symbol guard (run BEFORE deleting, once per symbol to confirm the audit):
`rg -rn "\b<name>\b" --glob '!*.pyc' --glob '!plans/**' --glob '!spec.md' --glob '!todo.md' .`
→ expected: exactly one hit (the definition). If a symbol shows extra hits,
STOP and report (drift from the audit).

Also check docs referencing deleted symbols: `rg -rn "send_via_whatsapp|sanitize_filename|get_session|WhatsApp" SPECIFICATIONS.md readme.md docs/`
→ if `SPECIFICATIONS.md` or `readme.md` mentions the WhatsApp placeholder or
the excel exporter, update the mention (one line) in the same change.

**Verify**: `rg -rn "add_items|get_item_count|get_total_quantity|update_supplier|verify_totals|update_identifier_9|update_name|update_receipt_id|from_dict|get_session|stop_scheduler|get_category_statistics|get_products_in_category|delete_inventory|get_product_profit_margin|send_via_whatsapp|get_date_range|handle_external_service|format_date|validate_integer_input|sanitize_filename|log_method|disconnect_from_event|get_available_events|validate_boolean|validate_email|validate_int_non_negative|validate_phone|validate_price_pair|validate_url|export_products|import_products" --glob '!*.pyc' --glob '!plans/**' --glob '!spec.md' --glob '!todo.md' .` → exit 1 (no matches).

### Step 2: Lint/format/type verification

**Verify**:
- `.venv/bin/ruff check .` → exit 0 (fix F401s as part of Step 1, not here)
- `.venv/bin/black --check .` → exit 0
- `.venv/bin/pyright` → exit 0

### Step 3: Full suite

**Verify**:
- `.venv/bin/python -m pytest` → all pass (modulo pre-existing worktree UI
  exceptions: 7 in `tests/test_ui/test_main_window_helpers.py`, 4 backup tests)
- `.venv/bin/bandit -q -r database services utils --skip B101` → exit 0

## Test plan

No new tests: the deleted symbols had zero references, so nothing pins them.
The full suite is the regression gate. If any test FAILS because it referenced
a deleted symbol, STOP and report (the audit's "zero test hits" claim was
wrong for that symbol).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `rg` for the 33-symbol alternation (Step 1 verify command) exits 1 (no matches anywhere except plans/spec/todo)
- [ ] `.venv/bin/ruff check .` exits 0 (orphaned imports removed)
- [ ] `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] SPECIFICATIONS/readme don't reference deleted symbols (checked in Step 1)
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- Any of the 33 symbols shows more than one hit in the pre-deletion guard
  (the audit drifted — report the extra references).
- A test fails referencing a deleted symbol.
- Deleting a method orphans an import that is still used elsewhere (report —
  don't guess).
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- The zero-reference rule stays per AGENTS.md: new public methods need a
  caller or a test.
- The model mutation API deletion closes TECH-04 (round 1); if future work
  wants domain mutations in models, that's a new architecture decision —
  services stay the mutation boundary.
- Reviewer scrutiny: that no `# type: ignore`/`noqa` was added to silence
  deletion fallout, and that the 15 test-only symbols were left untouched.
