# Structural Quality Audit - 2026-04-07

## Scope and assumptions

This document consolidates the architectural and implementation audit focused on modularity, scalability, maintainability, robustness, and unnecessary complexity reduction.

Inferred context from the repository:

1. Project: `billing_inventory_system_new`
2. Stack: Python, PySide6 desktop UI, SQLite, pytest
3. Runtime model: local single-user desktop application with an in-process backup scheduler
4. Business-critical flows:
   1. sales creation, update, deletion, and cancellation
   2. purchase creation, update, and deletion
   3. inventory integrity and stock adjustments
   4. product and customer lifecycle
   5. audit logging and backup visibility
5. Constraints and invariants are primarily defined by:
   1. [AGENTS.md](../../AGENTS.md)
   2. [schema.sql](../../schema.sql)
   3. [database/database_manager.py](../../database/database_manager.py)
   4. [SPECIFICATIONS.md](../../SPECIFICATIONS.md)
   5. [tests/](../../tests)

This audit is intended to be sufficient input for future implementation work without repeating a second broad audit.

---

## 1) Executive Summary

The repository has a recognizable and mostly useful layering intent, but it is not consistently enforced. The strongest parts of the system are transactional discipline around the most critical mutation flows, explicit business invariants in repo documentation, a meaningful test suite around key workflows, and recent work on audit logging, backup hardening, and soft-delete support.

The repo is not mainly suffering from under-architecture or over-architecture. It is suffering from inconsistent architecture. The main issue is not absence of structure, but repeated erosion of boundaries in high-traffic parts of the codebase. The clearest examples are UI-aware service decorators, duplicated event emission from both services and views, a global refresh strategy in the main window, and partial coexistence of two analytics architectures.

The most dangerous weaknesses are:

1. service-layer coupling to presentation behavior
2. duplicated post-mutation side effects across layers
3. oversized sales workflow modules in both UI and service layers
4. inconsistent service contracts for read and mutation operations
5. manual cache invalidation and event sequencing that rely on discipline rather than enforced structure

Overall health: moderate, with good operational foundations but increasing change cost. Without structural cleanup, future feature work will slow down and regression risk will keep rising, especially around sales, purchases, and global UI refresh behavior.

Recommended immediate focus:

1. restore service/UI boundaries
2. make the service layer the single owner of post-commit events
3. normalize service contracts
4. reduce global refresh fan-out
5. extract the most complex sales workflows before adding more business logic

---

## 2) System Map

### Core modules and layers

1. Presentation layer
   1. Main shell and tab orchestration live in [ui/main_window.py](../../ui/main_window.py)
   2. Primary workflows live in large view modules such as [ui/sale_view.py](../../ui/sale_view.py), [ui/purchase_view.py](../../ui/purchase_view.py), [ui/customer_view.py](../../ui/customer_view.py), and [ui/product_view.py](../../ui/product_view.py)
2. Service layer
   1. Domain workflow orchestration lives in [services/sale_service.py](../../services/sale_service.py), [services/purchase_service.py](../../services/purchase_service.py), [services/inventory_service.py](../../services/inventory_service.py), [services/product_service.py](../../services/product_service.py), and [services/customer_service.py](../../services/customer_service.py)
   2. Cross-cutting write tracing lives in [services/audit_service.py](../../services/audit_service.py)
   3. Background operational work lives in [services/backup_service.py](../../services/backup_service.py)
3. Persistence layer
   1. shared connection and transaction management live in [database/database_manager.py](../../database/database_manager.py)
   2. schema and migration evolution live in [schema.sql](../../schema.sql) and [database/migrations.py](../../database/migrations.py)
4. Cross-cutting infrastructure
   1. events live in [utils/system/event_system.py](../../utils/system/event_system.py)
   2. exception handling and dialogs are mixed in [utils/decorators.py](../../utils/decorators.py)
   3. validation lives primarily in [utils/validation](../../utils/validation)
5. Analytics
   1. existing production-style query service in [services/analytics_service.py](../../services/analytics_service.py)
   2. newer metric engine in [services/analytics/engine.py](../../services/analytics/engine.py) and [services/analytics/metrics.py](../../services/analytics/metrics.py)

### Dependency direction in practice

Nominal direction is:

1. UI -> services -> database/models/utils

Actual runtime dependency flow also includes:

1. services -> event system -> main window -> broad UI refresh -> services again
2. UI -> services -> service emits event
3. UI -> emits the same event again in several views

### Main hotspots and choke points

1. [services/sale_service.py](../../services/sale_service.py)
2. [ui/sale_view.py](../../ui/sale_view.py)
3. [ui/main_window.py](../../ui/main_window.py)
4. [utils/decorators.py](../../utils/decorators.py)
5. [services/analytics_service.py](../../services/analytics_service.py)
6. [services/purchase_service.py](../../services/purchase_service.py)

---

## 3) Findings Table

| ID | Area | Severity | Category | Problem | Why it matters | Evidence | Recommended fix | Expected benefit | Risk of change |
|---|---|---|---|---|---|---|---|---|---|
| SQ-1 | Cross-layer boundaries | High | Modularity, Maintainability | Service methods are decorated to show dialogs and some services import `UIException` | Domain code is harder to reuse, test, or invoke from non-UI entry points | [utils/decorators.py](../../utils/decorators.py), [services/product_service.py](../../services/product_service.py), [services/inventory_service.py](../../services/inventory_service.py), [services/sale_service.py](../../services/sale_service.py) | Remove dialog behavior from service layer and keep user messaging in UI/presenter code | Cleaner layering and easier future reuse | Medium |
| SQ-2 | Event ownership | High | Robustness, Complexity | UI and services both emit domain events for the same mutations | Duplicate refresh and unclear ownership of successful mutation side effects | [services/customer_service.py](../../services/customer_service.py), [ui/customer_view.py](../../ui/customer_view.py), [services/product_service.py](../../services/product_service.py), [ui/product_view.py](../../ui/product_view.py), [ui/purchase_view.py](../../ui/purchase_view.py) | Make services or workflow objects the only source of post-commit domain events | Predictable event model and less duplicate work | Low |
| SQ-3 | Global refresh | High | Scalability, Maintainability | MainWindow refreshes nearly every refreshable view on every relevant event | Unrelated changes trigger unrelated queries and rerenders; the cost scales with more views | [ui/main_window.py](../../ui/main_window.py) | Replace broad refresh with targeted routing by entity and affected tabs | Lower UI churn and clearer dependencies | Medium |
| SQ-4 | Sales domain hub | High | Complexity, Robustness | `SaleService` orchestrates validation, persistence, inventory mutation, receipt logic, audit logging, cache invalidation, and events | High blast radius and hard-to-isolate regression surface | [services/sale_service.py](../../services/sale_service.py) | Extract workflow objects and smaller policies/helpers | Lower regression risk and better cohesion | Medium |
| SQ-5 | Service contract inconsistency | High | Maintainability, Robustness | `get_*` methods do not share one failure model and some methods over-wrap exceptions | Callers need service-specific defensive logic and bugs are easier to mask | [services/product_service.py](../../services/product_service.py), [services/customer_service.py](../../services/customer_service.py), [services/sale_service.py](../../services/sale_service.py), [services/purchase_service.py](../../services/purchase_service.py) | Standardize service contracts for reads and mutations | Easier caller code and safer extension | Medium |
| SQ-6 | Cache invalidation model | Medium | Robustness, Complexity | Cache clearing is manual and tied to custom finalize patterns | Correctness relies on remembering a convention instead of using one enforced mechanism | [services/inventory_service.py](../../services/inventory_service.py), [services/sale_service.py](../../services/sale_service.py), [services/purchase_service.py](../../services/purchase_service.py), [services/analytics_service.py](../../services/analytics_service.py) | Centralize post-commit invalidation and notifications | Lower stale-data risk | Medium |
| SQ-7 | Sales UI size | Medium | Complexity, Maintainability | `SaleView` is a multi-responsibility UI monolith | Difficult to test, review, and extend safely | [ui/sale_view.py](../../ui/sale_view.py) | Split current sale entry, history, and actions into smaller units | Higher cohesion and safer future changes | High |
| SQ-8 | Dual analytics architecture | Medium | Modularity, Maintainability | Two analytics designs coexist, but the cleaner one is mostly used only by tests | Conceptual duplication and unclear target direction | [services/analytics_service.py](../../services/analytics_service.py), [services/analytics/engine.py](../../services/analytics/engine.py), [tests/analytics/test_metrics.py](../../tests/analytics/test_metrics.py) | Choose one architecture and migrate incrementally | Less conceptual overhead | Medium |
| SQ-9 | Purchase service duplication | Medium | Complexity, Maintainability | `PurchaseService` defines `_get_product_ids` twice | Silent override indicates module drift and weak hygiene | [services/purchase_service.py](../../services/purchase_service.py) | Remove duplicate helper and split commands from queries | Lower confusion and simpler maintenance | Low |
| SQ-10 | Background runtime scaling | Medium | Robustness, Scalability | Backup scheduler and shared DB runtime are adequate now but will not age well with more background work or a much larger DB | UI responsiveness and lock contention risks increase over time | [services/backup_service.py](../../services/backup_service.py), [database/database_manager.py](../../database/database_manager.py) | Add instrumentation first and isolate future background jobs if needed | Better confidence under growth | Medium |

---

## 4) Top 10 Structural Problems

### SQ-1: Service layer leaks presentation concerns

Diagnosis:
Service methods are decorated through [utils/decorators.py](../../utils/decorators.py) in a way that can trigger UI dialogs below the UI layer. Some services also import `UIException` directly.

Root cause:
Convenience-oriented decorator reuse blurred the separation between domain logic and presentation behavior.

Impacted modules:

1. [utils/decorators.py](../../utils/decorators.py)
2. [services/product_service.py](../../services/product_service.py)
3. [services/inventory_service.py](../../services/inventory_service.py)
4. [services/sale_service.py](../../services/sale_service.py)
5. [services/purchase_service.py](../../services/purchase_service.py)

Why this is a problem now:
The service layer is harder to reason about and harder to use safely from tests, background jobs, or future entry points.

Why this gets worse later:
Any future non-UI entry point will inherit Qt-specific behavior or require special handling.

Refactor direction:
Keep service methods pure from user-facing dialogs and move the dialog decision to UI adapters.

Safer migration path:

1. Remove `show_dialog=True` from service decorators in one service family at a time.
2. Let views catch and present user-facing errors.
3. Remove direct `UIException` imports from services once callers are updated.

### SQ-2: Event ownership is duplicated across layers

Diagnosis:
Several services emit domain events after a successful mutation, but UI views also emit the same events after calling those services.

Root cause:
No explicit architectural rule currently states which layer owns post-commit event emission.

Impacted modules:

1. [services/customer_service.py](../../services/customer_service.py)
2. [ui/customer_view.py](../../ui/customer_view.py)
3. [services/product_service.py](../../services/product_service.py)
4. [ui/product_view.py](../../ui/product_view.py)
5. [services/purchase_service.py](../../services/purchase_service.py)
6. [ui/purchase_view.py](../../ui/purchase_view.py)

Why this is a problem now:
It creates duplicate refresh behavior and hides the real owner of mutation completion.

Why this gets worse later:
As more side effects attach to events, duplicate emission becomes more expensive and harder to debug.

Refactor direction:
The service layer or explicit workflow layer should be the only owner of post-commit domain events.

Safer migration path:

1. Remove UI-side emissions first.
2. Add tests ensuring one event per mutation.

### SQ-3: MainWindow uses broad refresh fan-out

Diagnosis:
The main window subscribes to many events and refreshes every refreshable tab instead of routing refresh only where needed.

Root cause:
Centralized convenience refresh logic was cheaper initially than explicit routing.

Impacted module:

1. [ui/main_window.py](../../ui/main_window.py)

Why this is a problem now:
Unrelated tabs requery data and rerender on every mutation.

Why this gets worse later:
The cost scales with feature count, not just data volume.

Refactor direction:
Route events to specific tabs or view groups, and avoid broad refresh loops.

Safer migration path:

1. Map each event to affected tabs.
2. Keep a temporary fallback path while coverage is added.

### SQ-4: SaleService is a god service

Diagnosis:
`SaleService` contains create, update, delete, cancel, receipt generation, inventory interaction, cache clearing, analytics invalidation, and event orchestration.

Root cause:
The sales flow is business-critical and accumulated responsibilities over time.

Impacted module:

1. [services/sale_service.py](../../services/sale_service.py)

Why this is a problem now:
Almost any sales change touches a large, side-effect-heavy surface area.

Why this gets worse later:
Refunds, promotions, discounts, or more operational rules will make it even harder to evolve safely.

Refactor direction:
Extract mutation workflows and move calculations, validations, and post-commit behavior into narrower collaborators.

Safer migration path:

1. Start with `update_sale` because it has the highest accidental complexity.
2. Then extract shared post-commit logic.
3. Leave low-risk query methods for a later pass.

### SQ-5: Service API contracts are inconsistent

Diagnosis:
Some `get_*` methods return `None` on missing records, while others raise `NotFoundException` or rewrap failures as `DatabaseException`.

Root cause:
Contracts evolved independently by module.

Impacted modules:

1. [services/product_service.py](../../services/product_service.py)
2. [services/customer_service.py](../../services/customer_service.py)
3. [services/sale_service.py](../../services/sale_service.py)
4. [services/purchase_service.py](../../services/purchase_service.py)

Why this is a problem now:
Callers need service-specific knowledge for common operations.

Why this gets worse later:
More workflows will encode more defensive branching and more ambiguous failure handling.

Refactor direction:
Normalize contracts for reads and for mutations.

Safer migration path:

1. Pick one contract for reads.
2. Update callers and tests module by module.

### SQ-6: Cache invalidation is manual and fragile

Diagnosis:
Caches in inventory, sales, purchases, and analytics are cleared through ad hoc finalize methods and direct calls.

Root cause:
Caching was introduced without a central invalidation policy.

Impacted modules:

1. [services/inventory_service.py](../../services/inventory_service.py)
2. [services/sale_service.py](../../services/sale_service.py)
3. [services/purchase_service.py](../../services/purchase_service.py)
4. [services/analytics_service.py](../../services/analytics_service.py)

Why this is a problem now:
A missed clear can expose stale data.

Why this gets worse later:
More caches and more side effects increase the amount of choreography required.

Refactor direction:
Create a small post-commit invalidation and notification coordinator.

Safer migration path:

1. Start with inventory, sales, and analytics.
2. Add assertions/tests for invalidation behavior.

### SQ-7: SaleView has low cohesion and high local complexity

Diagnosis:
One widget handles sale entry, barcode flow, history loading, editing, deletion, export, shortcuts, and help.

Root cause:
The UI optimized for one-screen operator convenience, but responsibilities were never separated.

Impacted module:

1. [ui/sale_view.py](../../ui/sale_view.py)

Why this is a problem now:
Even small UI changes require reading a very large file with mixed concerns.

Why this gets worse later:
Return and refund flows will likely increase branching even more.

Refactor direction:
Split the view into smaller widgets or presenters.

Safer migration path:

1. Extract the sale history/action zone first.
2. Keep the outer widget shell stable while internals are modularized.

### SQ-8: Analytics architecture is split between old and new models

Diagnosis:
The repo contains a newer read-only metric engine, but the main application still leans on the older query-heavy `AnalyticsService`.

Root cause:
The analytics refactor was started but not completed.

Impacted modules:

1. [services/analytics_service.py](../../services/analytics_service.py)
2. [services/analytics/engine.py](../../services/analytics/engine.py)
3. [services/analytics/metrics.py](../../services/analytics/metrics.py)

Why this is a problem now:
Maintainers have to understand both paths.

Why this gets worse later:
New analytics can be added inconsistently, duplicating query knowledge.

Refactor direction:
Converge analytics on one model.

Safer migration path:

1. Migrate one production metric at a time.
2. Keep outputs identical while tests are expanded.

### SQ-9: PurchaseService shows code drift and accidental duplication

Diagnosis:
The module defines `_get_product_ids` twice and mixes transactional mutation code with several query/report methods.

Root cause:
Incremental growth without cleanup.

Impacted module:

1. [services/purchase_service.py](../../services/purchase_service.py)

Why this is a problem now:
It reduces trust in the module and hides the true source of helper behavior.

Why this gets worse later:
More hidden overrides and inconsistent style make maintenance slower.

Refactor direction:
Remove duplicate helpers and separate mutation workflows from reporting queries.

Safer migration path:

1. Remove duplication first.
2. Split commands and queries second.

### SQ-10: Background runtime model is acceptable now, but not a strong growth shape

Diagnosis:
The backup scheduler is simple and largely correct, but it assumes a small local DB and limited background activity.

Root cause:
The runtime model targets a current single-user desktop footprint.

Impacted modules:

1. [services/backup_service.py](../../services/backup_service.py)
2. [database/database_manager.py](../../database/database_manager.py)

Why this is a problem now:
This is not an acute issue today, but it already deserves instrumentation.

Why this gets worse later:
Larger databases or more background jobs will make UI responsiveness and contention more visible.

Refactor direction:
Measure first, then isolate future background work if needed.

Safer migration path:

1. Add timing and visibility first.
2. Avoid changing the backup design before metrics justify it.

---

## 5) Complexity Hotspots

### Hotspot A: [services/sale_service.py](../../services/sale_service.py)

Primary hotspots:

1. `create_sale`
2. `update_sale`
3. `_finalize_sale_mutation`
4. `_validate_sale_items`

Signs of excessive complexity:

1. validation, calculations, SQL, inventory mutation, audit log, cache invalidation, and events are mixed in one service
2. sales update requires reversing old inventory and applying new inventory in one flow
3. side effects are distributed across transaction and post-transaction phases

Recommended target shape:

1. `CreateSaleWorkflow`
2. `UpdateSaleWorkflow`
3. small helpers for totals and profit calculations
4. centralized post-commit notifier

### Hotspot B: [ui/sale_view.py](../../ui/sale_view.py)

Primary hotspots:

1. `complete_sale`
2. `load_sales`
3. `create_sale_actions`
4. `delete_sale`
5. sale entry and history rendering in the same class

Signs of excessive complexity:

1. one widget handles too many operational modes
2. mixed UI construction, workflow logic, history loading, and operator helpers

Recommended target shape:

1. `CurrentSalePanel`
2. `SalesHistoryPanel`
3. `SaleActionsController` or equivalent presenter

### Hotspot C: [ui/main_window.py](../../ui/main_window.py)

Primary hotspots:

1. `create_tabs`
2. `connect_to_events`
3. `refresh_relevant_views`

Signs of excessive complexity:

1. broad event subscriptions
2. global refresh loop that hides dependencies

Recommended target shape:

1. tab refresh routing table
2. event-to-view mapping
3. optional lazy tab initialization

### Hotspot D: [services/analytics_service.py](../../services/analytics_service.py)

Primary hotspots:

1. many near-identical query methods with repeated decorators and validation patterns

Signs of excessive complexity:

1. repetitive query wrapper pattern
2. manual cache clearing method listing each cached function

Recommended target shape:

1. metric registry or adapters over [services/analytics/engine.py](../../services/analytics/engine.py)

### Hotspot E: [services/purchase_service.py](../../services/purchase_service.py)

Primary hotspots:

1. `update_purchase`
2. `_finalize_purchase_mutation`
3. duplicate `_get_product_ids`

Signs of excessive complexity:

1. inventory reversal and reapplication
2. duplicated helper indicates drift
3. command and query responsibilities mixed together

Recommended target shape:

1. `PurchaseMutationWorkflow`
2. reporting/query helpers moved separately

---

## 6) Coupling / Cohesion Analysis

### Modules that are too coupled

1. [services/sale_service.py](../../services/sale_service.py)
   1. coupled to inventory, products, customers, receipts, analytics cache, audit logging, and events
2. [ui/main_window.py](../../ui/main_window.py)
   1. coupled to many event types and therefore indirectly to most mutation paths
3. [utils/decorators.py](../../utils/decorators.py)
   1. couples generic exception handling with Qt dialog behavior

### Modules with low cohesion

1. [ui/sale_view.py](../../ui/sale_view.py)
2. [services/analytics_service.py](../../services/analytics_service.py)
3. [services/purchase_service.py](../../services/purchase_service.py)

### God objects / god services / dumping grounds

1. [services/sale_service.py](../../services/sale_service.py)
2. [ui/sale_view.py](../../ui/sale_view.py)
3. [ui/main_window.py](../../ui/main_window.py)

### Boundary violations

1. service code can display user dialogs through decorators
2. some services import `UIException`
3. UI views emit domain events that services already emit

### Circular or quasi-circular runtime patterns

There is no dominant import cycle, which is good.

However, there is a runtime feedback loop:

1. service mutation emits event
2. main window refreshes many views
3. views reload through services

This is not a circular import issue, but it is a coupling and observability issue.

---

## 7) Robustness Gaps

### Invalid input and contract handling

1. read-method behavior is inconsistent across services
2. broad exception wrapping makes some failure semantics less explicit

### State consistency and transactionality

Strength:

1. critical sale and purchase mutations use transaction scopes correctly

Gap:

1. cache invalidation and event emission are not enforced by one central post-commit mechanism

### Retry and idempotency concerns

1. no major unsafe retry loop was found in business workflows
2. however, domain event duplication effectively creates duplicate side effects at the UI level

### Concurrency hazards

1. background backup and shared DB runtime are acceptable for current scale
2. further background work would need stronger isolation and observability

### External dependency failure handling

1. backup failure is surfaced better than before through `backup_skipped`
2. dependency/tooling drift still exists in repo docs and setup signals outside the scope of this structural document

### Logging / observability blind spots

1. main-window refresh fan-out makes it hard to identify which mutation caused which view reload cost
2. actor attribution in [services/audit_service.py](../../services/audit_service.py) is still optional, so accountability remains partial until authentication is implemented

---

## 8) Refactoring Roadmap

### Phase A - Quick Wins

Objective:
Reduce duplicated side effects and clarify contracts with low regression risk.

Specific tasks:

1. remove UI-side emission of domain events where services already emit them
2. remove the duplicate helper from [services/purchase_service.py](../../services/purchase_service.py)
3. standardize `get_*` method contracts in product, customer, sale, and purchase services
4. add focused tests for single-event emission and missing-record contracts

Dependencies:

1. none beyond current test coverage

Risk level:

1. low

Expected payoff:

1. high

Suggested order:

1. event ownership
2. service contract normalization
3. purchase service cleanup

### Phase B - Structural Refactors

Objective:
Re-establish clean boundaries and reduce god-module pressure.

Specific tasks:

1. remove dialog ownership from service decorators
2. introduce targeted refresh routing in [ui/main_window.py](../../ui/main_window.py)
3. extract `UpdateSaleWorkflow` and `DeleteSaleWorkflow`
4. separate product and customer query/mutation responsibilities where useful

Dependencies:

1. Phase A should land first

Risk level:

1. medium

Expected payoff:

1. very high

Suggested order:

1. decorators and boundary cleanup
2. main-window refresh routing
3. sale workflow extraction

### Phase C - Hardening

Objective:
Reduce hidden correctness risk around caches, invariants, and accountability.

Specific tasks:

1. centralize post-commit cache invalidation and notifications
2. add tests for stale-cache prevention
3. tighten soft-delete query discipline
4. prepare audit actor propagation once authentication exists

Dependencies:

1. structural refactors from Phase B

Risk level:

1. medium

Expected payoff:

1. high

Suggested order:

1. invalidation coordinator
2. tests
3. actor propagation support

### Phase D - Scalability Prep

Objective:
Prepare the codebase for more features and higher runtime load without rewriting it.

Specific tasks:

1. converge analytics on one architecture
2. lazy-load heavy tabs and avoid refreshing inactive tabs
3. instrument backup duration and refresh duration
4. revisit background-job isolation only after metrics justify it

Dependencies:

1. earlier phases

Risk level:

1. medium

Expected payoff:

1. medium now, higher later

Suggested order:

1. targeted UI loading
2. analytics convergence
3. instrumentation

---

## 9) Suggested Target Architecture

The recommended target is an incremental evolution, not a rewrite.

### Target direction

1. Presentation widgets and dialogs
2. UI controllers or presenters for workflow coordination
3. application workflow services for mutations
4. domain policies/helpers for validation, pricing, and stock rules
5. query/repository helpers over `DatabaseManager`
6. infrastructure services for events, logging, analytics execution, and backups

### Key architectural goals

1. clearer boundaries between domain logic and UI feedback
2. one owner for post-commit events
3. smaller mutation workflows around sales and purchases
4. explicit refresh routing instead of global refresh fan-out
5. one analytics architecture instead of two parallel paths

### Trade-offs

1. this introduces a few more focused modules, but reduces accidental complexity materially
2. the goal is not to fragment the codebase into micro-abstractions
3. extraction should follow real responsibility boundaries, not file-count aesthetics

---

## 10) Concrete Refactor Candidates

### RC-1: Remove UI-side event emission from mutation views

Rationale:
Services already emit successful post-commit events in multiple flows.

Expected gain:
Single-source event ownership and fewer duplicate refreshes.

Possible downside:
Some UI tests will need to stop expecting view-driven event emission.

Priority:
Now

### RC-2: Remove dialog behavior from service decorators

Rationale:
The service layer should not decide user-facing dialog behavior.

Expected gain:
Better reuse and clearer boundaries.

Possible downside:
UI call sites become a little more explicit.

Priority:
Now

### RC-3: Normalize `get_*` contracts across services

Rationale:
Callers should not need to know different missing-record semantics per service.

Expected gain:
Cleaner call sites and lower error-handling ambiguity.

Possible downside:
Requires coordinated updates to tests and some callers.

Priority:
Now

### RC-4: Extract `UpdateSaleWorkflow`

Rationale:
`update_sale` is the highest accidental complexity point in the domain layer.

Expected gain:
Better testability and lower regression risk.

Possible downside:
Moderate refactor effort.

Priority:
Now

### RC-5: Centralize post-commit invalidation and notifications

Rationale:
Current cache and event orchestration is manual and duplicated.

Expected gain:
Lower stale-data risk and less boilerplate.

Possible downside:
Adds one infrastructure concept.

Priority:
Now

### RC-6: Route refreshes by entity instead of refreshing all views

Rationale:
Global refresh will become more expensive and harder to reason about.

Expected gain:
Lower UI work and clearer dependency mapping.

Possible downside:
Requires identifying affected tabs per event.

Priority:
Soon

### RC-7: Split `SaleView`

Rationale:
The current view is too large and too mixed in responsibility.

Expected gain:
Higher cohesion and safer iteration.

Possible downside:
This is a visible UI refactor and should be staged carefully.

Priority:
Soon

### RC-8: Converge analytics on the metric engine

Rationale:
The repo already contains a better analytics shape.

Expected gain:
Reduced conceptual duplication and clearer extension point.

Possible downside:
Migrating reports may touch several views and tests.

Priority:
Soon

### RC-9: Split `PurchaseService` into mutations and queries

Rationale:
The module already shows drift and duplication.

Expected gain:
Simpler maintenance surface.

Possible downside:
Some file moves and import churn.

Priority:
Now

### RC-10: Add architectural regression tests

Rationale:
Current tests protect flows, but not all structural contracts.

Expected gain:
Prevents reintroduction of duplicate events and contract drift.

Possible downside:
Needs some targeted mocking.

Priority:
Now

---

## What should be refactored now, later, or left alone

### Refactor now

1. event ownership duplication
2. service/UI boundary leakage
3. inconsistent service contracts
4. `SaleService.update_sale`
5. duplicate helper drift in `PurchaseService`

### Refactor later

1. `SaleView` decomposition
2. analytics convergence
3. startup and lazy-loading improvements
4. backup/runtime scaling changes

### Leave alone for now

1. the overall transaction manager shape in [database/database_manager.py](../../database/database_manager.py)
2. the SQLite-native backup approach in [services/backup_service.py](../../services/backup_service.py)
3. the persistent audit log concept in [services/audit_service.py](../../services/audit_service.py)

---

## Resume Instructions

This file is the source document for future implementation work on structural quality.

Use it together with the backlog document:

1. [docs/audit/structural_quality_backlog.md](../audit/structural_quality_backlog.md)
2. [AGENTS.md](../../AGENTS.md)

Suggested prompts for a future conversation:

1. `Implement Phase SQ-A from docs/audit/structural_quality_backlog.md`
2. `Implement SQ-A.1 and SQ-A.2 from docs/audit/structural_quality_backlog.md`
3. `Review what was implemented for SQ-B.1 in docs/audit/structural_quality_backlog.md`

No second broad audit should be necessary before starting implementation if the work follows this document and its backlog.