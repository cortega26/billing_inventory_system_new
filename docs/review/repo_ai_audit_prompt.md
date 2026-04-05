# Repo-Specific AI Audit Prompt

Use the prompt below when asking an AI coding agent to audit and harden this repository. It is intentionally grounded in the current repo state so the audit starts from concrete signals instead of generic advice.

## Current Repo Context

- Domain: inventory and billing system for a Chilean minimarket.
- Stack: Python, `PySide6` desktop UI, SQLite, service/model/ui layering, pytest-based tests.
- Key areas:
  - `services/` for business logic
  - `models/` for domain entities
  - `database/`, `schema.sql`, and `database/__init__.py` for persistence and initialization
  - `ui/` for PySide6 workflows
  - `utils/` for validation, logging, decorators, helpers, and system abstractions
  - `tests/` for regression protection
  - `SPECIFICATIONS.md` and `docs/review/` for requirements and prior findings
- Root `AGENTS.md` exists and must be treated as a durable contributor and agent contract for this repo.

## Baseline Signals To Verify

- `pytest` currently fails during collection in the active environment because `reportlab` is missing.
- `ruff` is configured in `pyproject.toml`, but the active shell cannot resolve it without switching Python toolchains.
- pytest configuration is duplicated between `pyproject.toml` and `pytest.ini`.
- `SPECIFICATIONS.md` says the UI should be English only, while parts of the UI are currently in Spanish.
- Backup behavior appears inconsistent across `SPECIFICATIONS.md`, `config.py`, and `docs/review/security_findings.md`.
- `DatabaseManager.execute_query()` commits immediately, which increases partial-failure risk in multi-step flows if callers assume outer transaction boundaries are still atomic.

## Prompt

```text
You are auditing and hardening an existing repository for a desktop billing and inventory system.

Project context:
- Domain: inventory and billing system for a Chilean minimarket.
- Stack: Python, PySide6 desktop UI, SQLite database, service/model/ui layering, pytest-based tests.
- Important repo areas:
  - `services/` for business logic
  - `models/` for domain entities
  - `database/` and `schema.sql` for persistence and integrity rules
  - `ui/` for PySide6 views and user workflows
  - `utils/` for decorators, validation, logging, helpers, and system abstractions
  - `tests/` for automated verification
  - `SPECIFICATIONS.md`, `docs/review/`, and `AGENTS.md` for requirements, known findings, and engineering guardrails

Your mission:
Perform a deep, evidence-based audit of the repository and raise it to industry-grade quality.

Objectives:
1. Search for and fix bugs, inconsistencies, unexpected behaviors, sad-path failures, edge-case issues, and any other undesired behavior.
2. Improve robustness, clarity, modularity, maintainability, scalability, and performance.
3. Identify the 5 quickest wins and the 5 most critical updates.
4. Produce an implementation plan and a detailed backlog.
5. Raise the overall quality of the app to industry-grade.
6. Enforce strong software engineering best practices, including DRY, SOLID, separation of concerns, defensive programming, and explicit boundaries between UI, services, persistence, and validation.
7. Update `AGENTS.md` with durable engineering guardrails for future contributors and agents if the audit uncovers new truths or contradictions.
8. Prevent regressions through tests, validation, stronger invariants, and documented contracts.

Mandatory `AGENTS.md` work:
- Review `AGENTS.md` before making changes.
- Update it whenever the audit changes source-of-truth decisions, contracts, invariants, transaction expectations, or regression guardrails.
- Keep it specific to this repo rather than turning it into generic team process guidance.

Audit requirements:
- Inspect the codebase end to end, not just the happy path.
- Review both code and behavior: architecture, correctness, data integrity, transaction safety, error handling, validation, logging, configuration, tests, UX flows, dependency/setup reliability, and performance hotspots.
- Validate the current repository against its own specs and docs, and call out where documentation conflicts with implementation.
- Use `docs/review/` as input to verify, extend, or refute, not as unquestioned truth.
- Pay special attention to:
  - UI/service/database coupling
  - singleton/global state usage
  - transaction boundaries and partial-failure risk
  - duplicated or conflicting configuration
  - cache invalidation risks
  - schema constraints vs service-layer validation
  - sad paths and recovery behavior
  - oversized classes and mixed responsibilities
  - correctness of stock, sales, purchases, totals, and monetary calculations
  - startup reliability, backup behavior, and dependency/tooling drift
  - test gaps that allow regressions in core flows

Known repo signals that must be verified:
- `pytest` currently stops during collection because `reportlab` is missing in the active environment.
- `ruff` is not available in the active environment even though lint config exists in `pyproject.toml`.
- There is duplicated pytest configuration in `pyproject.toml` and `pytest.ini`.
- `SPECIFICATIONS.md` says the UI should be English only, but UI strings appear mixed-language.
- Backup expectations appear inconsistent between specs, config defaults, and review docs.
- `DatabaseManager.execute_query()` auto-commits, so any service flow that expects multi-step atomicity must be verified carefully.
Do not assume these are the only issues.

Execution expectations:
- First establish the baseline:
  - inspect structure and architecture
  - run tests, lint, and safe static checks available in the environment
  - summarize current failures, setup blockers, and likely causes
- Then perform the audit and implement low-risk, clearly correct fixes directly.
- For higher-risk or broader changes, describe the remediation precisely and place it in the backlog with priority, rationale, dependencies, and acceptance criteria.
- Add or improve regression protection whenever behavior is fixed or clarified:
  - unit tests
  - integration tests
  - contract checks
  - schema assertions
  - invariants in code
  - contributor guidance in `AGENTS.md`
- Do not make cosmetic-only changes unless they materially improve clarity, correctness, maintainability, or regression resistance.

Required outputs:
1. Findings first, ordered by severity, each with:
   - title
   - severity
   - impact
   - evidence
   - affected files
   - recommended fix
2. A “5 Quickest Wins” section.
3. A “5 Most Critical Updates” section.
4. A concrete implementation plan, sequenced by dependency and risk.
5. A detailed backlog with:
   - item
   - priority
   - why it matters
   - estimated effort
   - dependencies
   - acceptance criteria
   - regression protection required
6. A summary of fixes actually implemented during the audit.
7. A verification section covering:
   - tests run
   - checks run
   - results
   - remaining risks or blockers
8. A summary of `AGENTS.md` updates:
   - source-of-truth decisions
   - documented contracts
   - documented invariants
   - documented guardrails

Regression-prevention standard:
- Every bug fix should either add a test, tighten an invariant, improve a contract boundary, or be explicitly justified if none is possible.
- Every critical flow must be covered against both happy path and sad path where practical.
- Prefer changes that make invalid states harder to represent.
- Call out any area where regressions remain likely and specify what should be added next to reduce that risk.

Working style:
- Be rigorous and skeptical.
- Prefer root-cause fixes over superficial patches.
- Prefer simpler designs with stronger invariants.
- Preserve valid working behavior unless there is a compelling reason to change it.
- Call out assumptions explicitly.
- Use concrete file references and examples throughout.
```

## Expected Audit Coverage

- Startup, database initialization, and backup scheduler behavior.
- CRUD and edge cases for products, customers, sales, purchases, categories, inventory, and analytics.
- Monetary rounding, quantity precision, stock consistency, and transactional rollback behavior.
- Sad paths such as invalid inputs, missing dependencies, DB constraint failures, partial write failures, stale caches, and UI error handling.
- Alignment between `AGENTS.md`, `SPECIFICATIONS.md`, schema rules, service behavior, and tests.
