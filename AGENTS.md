# AGENTS.md

This file is the contributor and agent contract for this repository. Read it before changing behavior, persistence, tests, or documentation.

## Source Of Truth

Use these sources in this order, and reconcile them when they conflict:

1. Persisted invariants:
   `schema.sql`, `database/__init__.py`, and applied migrations define what the database can store.
2. Runtime business rules:
   `services/`, `utils/validation/`, and `models/enums.py` define application-level validation, limits, and workflow rules that are not fully enforced in SQLite.
3. Executable regression expectations:
   `tests/` defines the expected observable behavior and must be updated when intentional behavior changes.
4. Product and operational intent:
   `SPECIFICATIONS.md` and `docs/review/` describe desired behavior, constraints, and known concerns.
5. Local configuration defaults:
   `config.py` and `app_config.json` define runtime defaults such as theme and backup settings.

When these sources disagree, do not patch only one place. Either:

- align code, docs, and tests in the same change, or
- document the discrepancy explicitly in the PR and add the reconciliation work to the backlog.

Current known contradictions that must not be ignored:

- pytest configuration is duplicated between `pyproject.toml` and `pytest.ini`.

## Architecture Contracts

Honor these boundaries unless you are intentionally refactoring them and updating tests plus this file:

- `ui/` owns widgets, shortcuts, status messages, and interaction flow.
  UI code should not implement persistence rules directly.
- `services/` owns business workflows, validation orchestration, event emission, cache clearing, and cross-entity behavior.
  Service methods are the default entry points for domain mutations.
- `database/` owns connection management, schema initialization, migrations, and SQL execution helpers.
- `models/` owns domain data structures and DB row mapping.
- `utils/validation/` owns reusable input validation and normalization primitives.
- `services/analytics/` is read-only by contract.
  It should never mutate business tables.

Preferred dependency direction:

- UI -> services -> database/models/utils
- Services may depend on other services when the workflow truly spans domains, but avoid circular or hidden side effects.
- Tests may exercise any layer, but should make the target layer explicit.

## Domain Invariants

These rules are business critical and should be protected by schema, validation, and tests whenever practical:

- Money is CLP integer-only.
  Prices and totals must not have decimals.
- Maximum money value is `1_000_000` CLP.
  See `models/enums.py` and validators.
- Quantities allow at most 3 decimal places.
  See `QUANTITY_PRECISION`.
- Inventory must never become negative.
  Any sale, delete, update, or adjustment flow must preserve this.
- Every product should have a corresponding inventory row after creation.
- Sales decrease inventory exactly once.
  Voids and sale deletions must restore inventory exactly once.
- Purchases increase inventory exactly once.
  Purchase deletions and edits must reverse and reapply inventory exactly once.
- Sales may be edited or deleted regardless of age.
  Do not reintroduce time-window restrictions without updating specs, UI behavior, and regression tests together.
- Customer `identifier_9` must remain unique, 9 digits, and start with `9`.
- Customer `identifier_3or4`, when present, must remain 3 or 4 digits and not start with `0`.
- Analytics metrics are read-only and must not rely on side effects.
- Historical sales and purchase data are part of the inventory ledger.
  Do not destroy history casually to make deletes convenient.
- Products with sale or purchase history must not be deleted.
  Use archive/hide behavior instead of removing ledger rows.
- Historical sales may legitimately have `customer_id = NULL` after customer deletion.
  Service, model, reporting, and UI code must handle deleted customers without crashing.

## Persistence And Transaction Guardrails

Be very careful with transactional assumptions in this repo.

- `DatabaseManager.execute_query()` and `DatabaseManager.executemany()` commit immediately only when no managed transaction is active.
- Inside `DatabaseManager.transaction()` or after `DatabaseManager.begin_transaction()`, query helpers participate in the current transaction and defer commit until the outer transaction completes.
- `DatabaseManager` serializes access with a process-local re-entrant lock.
  Treat transactions as thread-affine and do not expect concurrent writes on the shared connection to interleave safely.
- If a multi-step workflow must be atomic, verify that the implementation truly shares one managed transaction boundary.
- Emit domain/UI refresh events only after the transaction succeeds.
  Do not emit signals from the middle of a workflow that may still roll back.
- Any fix for partial-failure risk should come with focused regression coverage.

Before changing persistence behavior:

- update `schema.sql` for new installs
- update initialization or migration behavior in `database/__init__.py` or `database/migrations.py`
- add or update DB-focused tests in `tests/test_database/`
- add or update service-flow tests when the change affects runtime behavior

## High-Risk Areas

Changes in these areas require extra care and usually extra tests:

- `services/sale_service.py`
  Crosses sales, inventory, receipts, caching, and events.
- `services/purchase_service.py`
  Crosses purchases, inventory, product cost updates, caching, and events.
- `services/product_service.py`
  Product deletion interacts with history tables and can violate ledger expectations if handled casually.
- `services/inventory_service.py`
  Protects non-negative stock and quantity precision.
- `services/backup_service.py`
  Encodes retention, directory handling, scheduling, and SQLite backup semantics.
- `config.py`
  Central defaults, singleton behavior, runtime file IO, and backup policy live here.
- `database/database_manager.py`
  Affects transaction semantics across the whole app.

## Forbidden Shortcuts

Do not do the following without an explicit, fully tested refactor:

- Do not write SQL directly from `ui/`.
- Do not bypass service-layer validation for business mutations just because schema constraints exist.
- Do not add new business rules only to docs without enforcing them in code or tests.
- Do not change constants in `models/enums.py` without auditing validators, schema assumptions, and affected tests.
- Do not change backup interval or retention in only one file.
- Do not introduce or restore sale age restrictions in only one layer.
  Service rules, UI affordances, docs, and tests must stay aligned.
- Do not rely on cache-bearing service methods without confirming cache invalidation paths.
- Do not add new mutation workflows that emit no domain events if existing UI depends on refresh signals.
- Do not treat product deletion as harmless.
  It touches inventory history and can undermine auditability.
- Do not delete `sale_items` or `purchase_items` as a shortcut to make product deletion succeed.
- Do not assume every historical sale still has a live customer row.
- Do not rely on bare `python` or `ruff` being on PATH for repo automation.
  Prefer `.venv/bin/python` and `.venv/bin/ruff` unless the environment is known-good.

## Regression Prevention Rules

Every bug fix or behavior change must do at least one of these:

- add or update a unit test
- add or update an integration or service-flow test
- strengthen a validation rule or invariant
- strengthen a schema constraint or migration
- update `AGENTS.md` when the repo contract changes

Expected regression coverage by change type:

- Validator changes:
  update `tests/test_validation/`
- Database or transaction changes:
  update `tests/test_database/` and affected service-flow tests
- Product, customer, inventory, sale, or purchase logic:
  update `tests/test_services/` and `tests/test_critical_backend_flows.py` when the flow is cross-domain
- Config or backup behavior:
  update `tests/test_config.py`, `tests/test_system/test_config.py`, and backup tests as applicable
- Logger or event-system behavior:
  update matching system tests

When fixing a sad path:

- add a sad-path assertion if one does not already exist
- verify the failure does not leave partial writes or stale cache behind
- verify user-visible errors remain understandable if UI behavior is affected

## Documentation Guardrails

If you intentionally change behavior, update the relevant docs in the same change:

- `SPECIFICATIONS.md` for product rules and operational expectations
- `docs/review/` when a prior finding is resolved, superseded, or disproven
- `AGENTS.md` when source-of-truth decisions, contracts, invariants, or guardrails change
- setup docs when dependencies, Python version assumptions, or tooling commands change

Do not let `AGENTS.md`, tests, and implementation drift apart after a behavioral change.

## Practical Workflow For Agents

Before coding:

- read the relevant service, validator, schema, and tests
- identify whether the change affects invariants, transaction boundaries, or cache/event behavior
- check for contradictions in docs and config

Before finishing:

- run the narrowest meaningful tests first, then broader checks if available
- verify both happy path and sad path for the changed flow
- call out any remaining contradictions or follow-up backlog clearly

## Repo Notes Discovered During Setup

- The project virtualenv currently runs the full suite successfully.
  Prefer `.venv/bin/python -m pytest`.
- The current shell still does not expose `python` and `ruff` on PATH consistently.
  Prefer `.venv/bin/python` and `.venv/bin/ruff`.
- The repo currently mixes English and Spanish user-facing strings.
- New or modified top-level UI strings should be English until the remaining migration is complete.
- `pytest` currently uses `pytest.ini` and warns that pytest settings in `pyproject.toml` are ignored.
