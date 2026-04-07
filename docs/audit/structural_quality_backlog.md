# Structural Quality Backlog

> Source audit: [docs/review/structural_quality_audit_2026-04-07.md](../review/structural_quality_audit_2026-04-07.md)
> Purpose: resume implementation in a new conversation without re-auditing the repo

---

## How to use this backlog

This backlog is designed for incremental execution.

Recommended prompts:

1. `Implement Phase SQ-A from docs/audit/structural_quality_backlog.md`
2. `Implement only SQ-A.1 and SQ-A.2 from docs/audit/structural_quality_backlog.md`
3. `Review SQ-B.1 implementation against docs/review/structural_quality_audit_2026-04-07.md`

Execution rules:

1. Do not re-audit the repo broadly before starting unless the repo changed materially.
2. Follow invariants and guardrails in [AGENTS.md](../../AGENTS.md).
3. Prefer small, reversible batches.
4. Add regression protection whenever a behavior or contract changes.

---

## Already implemented in this stage

### SQ-A.1 Remove duplicated domain event emission from UI

- Status: completed
- Evidence:
  - [ui/customer_view.py](../../ui/customer_view.py)
  - [ui/product_view.py](../../ui/product_view.py)
  - [ui/purchase_view.py](../../ui/purchase_view.py)
  - [ui/main_window.py](../../ui/main_window.py)
  - [tests/test_ui/test_customer_view.py](../../tests/test_ui/test_customer_view.py)
  - [tests/test_ui/test_product_view.py](../../tests/test_ui/test_product_view.py)
  - [tests/test_ui/test_main_window_helpers.py](../../tests/test_ui/test_main_window_helpers.py)

### SQ-A.2 Normalize missing-record contracts in service reads

- Status: completed
- Evidence:
  - [services/customer_service.py](../../services/customer_service.py)
  - [services/product_service.py](../../services/product_service.py)
  - [services/sale_service.py](../../services/sale_service.py)
  - [services/purchase_service.py](../../services/purchase_service.py)
  - [tests/test_services/test_customer_service.py](../../tests/test_services/test_customer_service.py)
  - [tests/test_services/test_product_service.py](../../tests/test_services/test_product_service.py)
  - [tests/test_services/test_sale_service.py](../../tests/test_services/test_sale_service.py)
  - [tests/test_services/test_purchase_service.py](../../tests/test_services/test_purchase_service.py)

### SQ-A.3 Remove accidental duplication in PurchaseService

- Status: completed
- Evidence:
  - [services/purchase_service.py](../../services/purchase_service.py)
  - [tests/test_services/test_purchase_service.py](../../tests/test_services/test_purchase_service.py)

### SQ-A.4 Add architectural regression tests for event ownership

- Status: completed
- Evidence:
  - [tests/test_services/test_customer_service.py](../../tests/test_services/test_customer_service.py)
  - [tests/test_services/test_product_service.py](../../tests/test_services/test_product_service.py)
  - [tests/test_services/test_purchase_service.py](../../tests/test_services/test_purchase_service.py)
  - [tests/test_critical_backend_flows.py](../../tests/test_critical_backend_flows.py)

### SQ-B.1 Remove dialog ownership from service decorators

- Status: completed
- Evidence:
  - [utils/decorators.py](../../utils/decorators.py)
  - [services/product_service.py](../../services/product_service.py)
  - [services/inventory_service.py](../../services/inventory_service.py)
  - [tests/test_utils/test_decorators.py](../../tests/test_utils/test_decorators.py)
  - [tests/test_services/test_product_service.py](../../tests/test_services/test_product_service.py)
  - [tests/test_ui/test_product_view.py](../../tests/test_ui/test_product_view.py)

### SQ-B.2 Route refresh by affected view instead of refreshing everything

- Status: completed
- Evidence:
  - [ui/main_window.py](../../ui/main_window.py)
  - [tests/test_ui/test_main_window_helpers.py](../../tests/test_ui/test_main_window_helpers.py)

---

## Priority model

1. `P0`: do now, highest leverage or highest risk reduction
2. `P1`: next, structural improvement with moderate scope
3. `P2`: valuable, but should wait for prerequisites
4. `P3`: future optimization or scalability prep

Effort model:

1. `S`: up to one focused conversation
2. `M`: one to two conversations
3. `L`: staged work across several conversations

---

## Phase SQ-A - Quick Wins and Contract Cleanup

Objective:
Reduce duplicated side effects and standardize service behavior with low regression risk.

### SQ-A.1 Remove duplicated domain event emission from UI

- Priority: P0
- Effort: S
- Status: completed
- Findings covered:
  - SQ-2
  - SQ-3
- Why it matters:
  - services already emit post-commit domain events in customer, product, and purchase flows
  - UI-side re-emission causes duplicate refreshes and hides event ownership
- Main files:
  - [ui/customer_view.py](../../ui/customer_view.py)
  - [ui/product_view.py](../../ui/product_view.py)
  - [ui/purchase_view.py](../../ui/purchase_view.py)
  - [services/customer_service.py](../../services/customer_service.py)
  - [services/product_service.py](../../services/product_service.py)
  - [services/purchase_service.py](../../services/purchase_service.py)
- Tasks:
  1. remove `event_system.*.emit(...)` calls from views where the service already emits the same event
  2. confirm services remain the single owner of post-commit event emission
  3. review `MainWindow` behavior after event de-duplication
- Dependencies:
  - none
- Acceptance criteria:
  1. a successful mutation causes one domain event, not two
  2. product, customer, and purchase screens still refresh correctly
  3. no loss of user-facing success messaging
- Regression protection required:
  1. tests for one event emission per mutation path
  2. focused UI or service tests for affected views

### SQ-A.2 Normalize missing-record contracts in service reads

- Priority: P0
- Effort: M
- Status: completed
- Findings covered:
  - SQ-5
- Why it matters:
  - callers currently need service-specific knowledge to know whether a missing record is `None` or an exception
- Main files:
  - [services/product_service.py](../../services/product_service.py)
  - [services/customer_service.py](../../services/customer_service.py)
  - [services/sale_service.py](../../services/sale_service.py)
  - [services/purchase_service.py](../../services/purchase_service.py)
  - affected tests in [tests/test_services](../../tests/test_services)
- Tasks:
  1. choose a consistent contract for `get_*` methods
  2. update callers in UI and service code
  3. stop broad rewrapping that hides the chosen contract where possible
- Dependencies:
  - none
- Acceptance criteria:
  1. all main service `get_*` methods follow one consistent missing-record contract
  2. callers no longer need ad hoc service-specific handling
  3. tests document the chosen behavior explicitly
- Regression protection required:
  1. update service tests for missing-record cases
  2. add at least one cross-flow test proving callers still behave correctly

### SQ-A.3 Remove accidental duplication in PurchaseService

- Priority: P0
- Effort: S
- Status: completed
- Findings covered:
  - SQ-9
- Why it matters:
  - duplicate helper definitions reduce trust in the module and invite maintenance mistakes
- Main files:
  - [services/purchase_service.py](../../services/purchase_service.py)
  - [tests/test_services/test_purchase_service.py](../../tests/test_services/test_purchase_service.py)
- Tasks:
  1. remove the duplicate `_get_product_ids`
  2. leave behavior unchanged otherwise
  3. clean up related comments and structure if useful
- Dependencies:
  - none
- Acceptance criteria:
  1. `PurchaseService` contains one authoritative helper definition
  2. tests still pass for purchase flows
- Regression protection required:
  1. run focused purchase tests

### SQ-A.4 Add architectural regression tests for event ownership

- Priority: P0
- Effort: M
- Status: completed
- Findings covered:
  - SQ-2
  - SQ-3
- Why it matters:
  - current tests protect behavior, but not enough structural contracts
- Main files:
  - [tests/test_services/test_customer_service.py](../../tests/test_services/test_customer_service.py)
  - [tests/test_services/test_product_service.py](../../tests/test_services/test_product_service.py)
  - [tests/test_services/test_purchase_service.py](../../tests/test_services/test_purchase_service.py)
  - [tests/test_critical_backend_flows.py](../../tests/test_critical_backend_flows.py)
- Tasks:
  1. assert one event emission per mutation
  2. verify no duplicate UI-triggered event remains for affected flows
- Dependencies:
  - SQ-A.1
- Acceptance criteria:
  1. structural event ownership is covered by tests
  2. duplicate emission would fail tests
- Regression protection required:
  1. mocked event-system assertions or helper-based event capture

---

## Phase SQ-B - Boundary Restoration and Sales Refactor Foundations

Objective:
Re-establish clean boundaries and reduce the highest-value structural complexity.

### SQ-B.1 Remove dialog ownership from service decorators

- Priority: P1
- Effort: M
- Status: completed
- Findings covered:
  - SQ-1
- Why it matters:
  - the service layer should not own user-dialog behavior
- Main files:
  - [utils/decorators.py](../../utils/decorators.py)
  - [services/sale_service.py](../../services/sale_service.py)
  - [services/purchase_service.py](../../services/purchase_service.py)
  - [services/product_service.py](../../services/product_service.py)
  - [services/inventory_service.py](../../services/inventory_service.py)
  - [services/customer_service.py](../../services/customer_service.py)
  - affected UI callers under [ui/](../../ui)
- Tasks:
  1. stop showing dialogs from service-layer decorators
  2. move user-facing error presentation to views or UI wrappers
  3. remove `UIException` imports from services where no longer needed
- Dependencies:
  - SQ-A.2 helps
- Acceptance criteria:
  1. services can be invoked without Qt-dependent user-dialog side effects
  2. UI still surfaces understandable errors to operators
  3. service tests no longer implicitly depend on dialog suppression behavior
- Regression protection required:
  1. focused tests for service exceptions
  2. UI tests for visible error handling in key flows

### SQ-B.2 Route refresh by affected view instead of refreshing everything

- Priority: P1
- Effort: M
- Status: completed
- Findings covered:
  - SQ-3
- Why it matters:
  - current refresh fan-out scales poorly and hides dependencies
- Main files:
  - [ui/main_window.py](../../ui/main_window.py)
  - potentially [ui/dashboard_view.py](../../ui/dashboard_view.py)
  - potentially [ui/analytics_view.py](../../ui/analytics_view.py)
- Tasks:
  1. map domain events to affected tabs or refresh targets
  2. stop calling `refresh()` on every tab for every event
  3. keep a clear fallback path for truly global refreshes only when needed
- Dependencies:
  - SQ-A.1
- Acceptance criteria:
  1. product changes refresh product and dependent views only
  2. customer changes refresh customer and dependent views only
  3. inventory changes do not trigger unrelated heavy reloads
- Regression protection required:
  1. targeted MainWindow tests
  2. helper tests for refresh routing

### SQ-B.3 Extract `UpdateSaleWorkflow`

- Priority: P1
- Effort: L
- Findings covered:
  - SQ-4
  - SQ-6
- Why it matters:
  - `update_sale` is the highest accidental-complexity mutation in the codebase
- Main files:
  - [services/sale_service.py](../../services/sale_service.py)
  - new workflow/helper module under [services/](../../services)
  - [tests/test_services/test_sale_service.py](../../tests/test_services/test_sale_service.py)
  - [tests/test_critical_backend_flows.py](../../tests/test_critical_backend_flows.py)
- Tasks:
  1. extract inventory precheck, mutation steps, and post-commit behavior into a workflow object or clearly separated helpers
  2. keep transaction boundaries explicit
  3. keep emitted events after successful commit only
- Dependencies:
  - SQ-A.2
  - SQ-B.1 recommended
- Acceptance criteria:
  1. `SaleService.update_sale` is materially smaller and easier to read
  2. update flow behavior stays identical
  3. rollback and inventory consistency remain protected
- Regression protection required:
  1. focused update-sale tests
  2. sad-path tests for insufficient stock and rollback

### SQ-B.4 Extract common post-commit mutation behavior

- Priority: P1
- Effort: M
- Findings covered:
  - SQ-6
- Why it matters:
  - cache invalidation and event sequencing are currently manual and duplicated
- Main files:
  - [services/sale_service.py](../../services/sale_service.py)
  - [services/purchase_service.py](../../services/purchase_service.py)
  - [services/inventory_service.py](../../services/inventory_service.py)
  - [services/analytics_service.py](../../services/analytics_service.py)
- Tasks:
  1. create a small coordinator for cache clears and event emission after commit
  2. stop duplicating finalize patterns where practical
  3. document ordering rules in code and tests
- Dependencies:
  - SQ-B.1 preferred
- Acceptance criteria:
  1. mutation flows no longer manually repeat most invalidation logic
  2. sequence is explicit and tested
- Regression protection required:
  1. tests around cache clearing and event ordering

---

## Phase SQ-C - UI Decomposition and Analytics Convergence

Objective:
Reduce oversized modules and converge on cleaner extension points.

### SQ-C.1 Split SaleView into cohesive units

- Priority: P2
- Effort: L
- Status: completed
- Findings covered:
  - SQ-7
- Why it matters:
  - the sales UI is too large and mixed in responsibility
- Main files:
  - [ui/sale_view.py](../../ui/sale_view.py)
  - potential new modules under [ui/](../../ui)
  - sales UI tests under [tests/test_ui](../../tests/test_ui)
- Tasks:
  1. separate current-sale entry from history and actions
  2. move table rendering helpers out of the main widget
  3. keep shortcuts and operator behavior stable
- Dependencies:
  - SQ-B.2
  - SQ-B.3
- Acceptance criteria:
  1. `SaleView` becomes materially smaller
  2. extracted units have clear responsibilities
  3. sales UI behavior remains stable
- Regression protection required:
  1. UI helper tests
  2. interaction tests for core sales actions
- Evidence:
  - [ui/sale_view.py](../../ui/sale_view.py)
  - [ui/sale_view_support.py](../../ui/sale_view_support.py)
  - [ui/sale_view_tables.py](../../ui/sale_view_tables.py)
  - [tests/test_ui/test_sale_view_helpers.py](../../tests/test_ui/test_sale_view_helpers.py)
  - [tests/test_ui/test_sale_view_tables.py](../../tests/test_ui/test_sale_view_tables.py)
- Notes:
  - Current-sale customer entry, current-sale table rendering, and history/action table rendering were extracted incrementally without changing the public view contract.
  - Focused local validation no longer reports the previous structural warnings for [ui/sale_view.py](../../ui/sale_view.py).

### SQ-C.2 Converge analytics on one architecture

- Priority: P2
- Effort: L
- Status: completed
- Findings covered:
  - SQ-8
- Why it matters:
  - the repo currently contains two analytics mental models
- Main files:
  - [services/analytics_service.py](../../services/analytics_service.py)
  - [services/analytics/engine.py](../../services/analytics/engine.py)
  - [services/analytics/metrics.py](../../services/analytics/metrics.py)
  - [ui/analytics_view.py](../../ui/analytics_view.py)
  - [tests/analytics/test_metrics.py](../../tests/analytics/test_metrics.py)
- Tasks:
  1. decide whether the metric engine is the target architecture
  2. migrate one production analytics use case at a time
  3. remove or deprecate duplicated analytics queries only after migration is complete
- Dependencies:
  - SQ-A.2 recommended
- Acceptance criteria:
  1. one analytics extension model is clearly preferred and documented
  2. production analytics no longer depends on duplicated query definitions for migrated metrics
- Regression protection required:
  1. metrics tests
  2. analytics view smoke coverage
- Notes:
  - Decision: [services/analytics/engine.py](../../services/analytics/engine.py) plus [services/analytics/metrics.py](../../services/analytics/metrics.py) is now the preferred production analytics architecture. [services/analytics_service.py](../../services/analytics_service.py) remains as a compatibility facade over those metrics.
  - Incremental progress: [services/analytics_service.py](../../services/analytics_service.py) `get_sales_trend` now delegates to [services/analytics/engine.py](../../services/analytics/engine.py) through [services/analytics/metrics.py](../../services/analytics/metrics.py) `SalesDailyMetric` while preserving the existing public output shape.
  - Incremental progress: [services/analytics_service.py](../../services/analytics_service.py) `get_sales_by_weekday` now delegates to [services/analytics/engine.py](../../services/analytics/engine.py) through [services/analytics/metrics.py](../../services/analytics/metrics.py) `WeekdaySalesMetric`, preserving the weekday aggregation shape used by [ui/analytics_view.py](../../ui/analytics_view.py).
  - Incremental progress: [services/analytics_service.py](../../services/analytics_service.py) `get_top_selling_products` now delegates to [services/analytics/engine.py](../../services/analytics/engine.py) through [services/analytics/metrics.py](../../services/analytics/metrics.py) `TopProductsMetric`, preserving the product ranking shape used by [ui/analytics_view.py](../../ui/analytics_view.py) and keeping both `id` and `product_id` during the transition.
  - Incremental progress: [services/analytics_service.py](../../services/analytics_service.py) `get_category_performance` now delegates to [services/analytics/engine.py](../../services/analytics/engine.py) through [services/analytics/metrics.py](../../services/analytics/metrics.py) `DepartmentSalesMetric`, preserving the existing category-performance output shape by remapping `units_sold` to `number_of_products_sold`.
  - Incremental progress: [services/analytics_service.py](../../services/analytics_service.py) `get_profit_trend` now delegates to [services/analytics/engine.py](../../services/analytics/engine.py) through [services/analytics/metrics.py](../../services/analytics/metrics.py) `ProfitTrendMetric`, preserving the existing daily revenue/profit trend shape used by [ui/analytics_view.py](../../ui/analytics_view.py).
  - Completion: `get_weekly_profit_trend`, `get_profit_and_volume_by_product`, `get_profit_by_product`, `get_profit_margin_distribution`, and `get_sales_summary` now also delegate to metrics, so production analytics no longer depends on duplicated SQL definitions in [services/analytics_service.py](../../services/analytics_service.py).
  - Focused regression coverage for the compatibility facade lives in [tests/test_services/test_analytics_service.py](../../tests/test_services/test_analytics_service.py).
  - Metric-level coverage for the preferred architecture lives in [tests/analytics/test_metrics.py](../../tests/analytics/test_metrics.py).
  - Focused UI smoke coverage for migrated analytics contracts lives in [tests/test_ui/test_analytics_view.py](../../tests/test_ui/test_analytics_view.py), covering sales by weekday, category performance, and top-selling products without instantiating the QtCharts-heavy full view.

### SQ-C.3 Split PurchaseService commands from queries

- Priority: P2
- Effort: M
- Status: completed
- Findings covered:
  - SQ-9
- Why it matters:
  - the module mixes mutation workflows with reporting/history methods
- Main files:
  - [services/purchase_service.py](../../services/purchase_service.py)
  - any new query module under [services/](../../services)
- Tasks:
  1. separate mutation methods from reporting/query helpers
  2. keep public API stable where reasonable
- Dependencies:
  - SQ-A.3
- Acceptance criteria:
  1. purchase mutations and purchase reporting are easier to locate and review
- Regression protection required:
  1. focused purchase service tests
- Evidence:
  - [services/purchase_service.py](../../services/purchase_service.py)
  - [services/purchase_query_service.py](../../services/purchase_query_service.py)
  - [tests/test_services/test_purchase_service.py](../../tests/test_services/test_purchase_service.py)

### SQ-C.4 Reduce local complexity in ProductService and InventoryService

- Priority: P2
- Effort: M
- Status: completed
- Findings covered:
  - SQ-5
  - SQ-6
  - post-audit Codacy local complexity follow-up
- Why it matters:
  - implementation-time Codacy warnings currently flag `create_product`, `update_product`, `_validate_product_data`, and `apply_batch_updates`
  - those warnings are not covered explicitly by the remaining backlog items and will likely recur until helper boundaries are clearer
- Main files:
  - [services/product_service.py](../../services/product_service.py)
  - [services/inventory_service.py](../../services/inventory_service.py)
  - [tests/test_services/test_product_service.py](../../tests/test_services/test_product_service.py)
  - [tests/test_services/test_inventory_service.py](../../tests/test_services/test_inventory_service.py)
- Tasks:
  1. extract product validation and normalization helpers out of `create_product` and `update_product`
  2. reduce branching in `_validate_product_data` by separating field-specific rules from persistence-shape building
  3. simplify `apply_batch_updates` with a small item-normalization helper and narrower branching
  4. keep public service behavior unchanged while reducing local method size and decision count
- Dependencies:
  - SQ-B.1 completed
  - SQ-B.4 preferred
- Acceptance criteria:
  1. current Codacy local complexity and method-size warnings for these methods are resolved or reduced below the configured threshold
  2. product and inventory public service behavior remains unchanged
  3. tests document the sad-path and helper-boundary behavior explicitly
- Regression protection required:
  1. focused product service tests
  2. focused inventory service tests for batch updates and sad paths
- Evidence:
  - [services/product_service.py](../../services/product_service.py)
  - [services/product_service_support.py](../../services/product_service_support.py)
  - [services/inventory_service.py](../../services/inventory_service.py)
  - [tests/test_services/test_product_service.py](../../tests/test_services/test_product_service.py)
  - [tests/test_services/test_inventory_service.py](../../tests/test_services/test_inventory_service.py)
- Notes:
  - Focused Codacy validation on the edited files no longer reports the local method-size or cyclomatic warnings for `create_product`, `update_product`, `_validate_product_data`, or `apply_batch_updates`.
  - Follow-up extraction to [services/product_service_support.py](../../services/product_service_support.py) also removed the residual `product_service.py` `file-nloc` warning without changing the public service contract.

---

## Phase SQ-D - Hardening and Scalability Preparation

Objective:
Prepare the repo for growth without overengineering.

### SQ-D.1 Add targeted instrumentation for UI refresh cost and backup runtime

- Priority: P3
- Effort: S/M
- Findings covered:
  - SQ-3
  - SQ-10
- Why it matters:
  - performance work should be guided by measured cost, not guesses
- Main files:
  - [ui/main_window.py](../../ui/main_window.py)
  - [services/backup_service.py](../../services/backup_service.py)
  - logging helpers under [utils/system](../../utils/system)
- Tasks:
  1. log refresh duration for targeted refreshes
  2. log backup duration and basic health metadata
- Dependencies:
  - SQ-B.2 recommended
- Acceptance criteria:
  1. refresh and backup runtime become visible in logs
  2. future scalability decisions can use data
- Regression protection required:
  1. focused helper tests where practical

### SQ-D.2 Consider lazy initialization of heavy tabs

- Priority: P3
- Effort: M
- Findings covered:
  - SQ-3
  - SQ-7
- Why it matters:
  - eager creation of all tabs increases startup work and memory footprint
- Main files:
  - [ui/main_window.py](../../ui/main_window.py)
  - affected views under [ui/](../../ui)
- Tasks:
  1. identify heavy tabs first
  2. initialize them on first access if the UX remains acceptable
- Dependencies:
  - SQ-B.2
- Acceptance criteria:
  1. startup path does not instantiate all heavy views unnecessarily
  2. first-open behavior remains acceptable for operators
- Regression protection required:
  1. startup and tab-switch smoke tests

### SQ-D.3 Prepare audit actor propagation after authentication lands

- Priority: P3
- Effort: M
- Findings covered:
  - SQ-1
  - SQ-6
  - audit actor gap from source audit
- Why it matters:
  - audit log usefulness is limited until actor context is reliable
- Main files:
  - [services/audit_service.py](../../services/audit_service.py)
  - future authentication modules
  - critical mutation services
- Tasks:
  1. define actor propagation strategy
  2. thread actor context into mutation logging after auth exists
- Dependencies:
  - authentication feature work, not included in this backlog
- Acceptance criteria:
  1. critical mutations can be attributed to authenticated actors
- Regression protection required:
  1. audit log tests with actor assertions

---

## Suggested execution order

1. SQ-B.1
2. SQ-B.2
3. SQ-B.3
4. SQ-B.4
5. SQ-C.4
6. SQ-C.3
7. SQ-C.1
8. SQ-C.2
9. SQ-D.1
10. SQ-D.2
11. SQ-D.3

---

## Recommended first new-conversation prompts

1. `Implement Phase SQ-B from docs/audit/structural_quality_backlog.md`
2. `Implement SQ-B.1 from docs/audit/structural_quality_backlog.md with focused tests`
3. `Implement SQ-B.2 from docs/audit/structural_quality_backlog.md after reviewing MainWindow refresh behavior`
4. `Review Phase SQ-A implementation against docs/review/structural_quality_audit_2026-04-07.md and continue with SQ-B.1`

---

## Resume set

If this work resumes in a future conversation, start from:

1. [docs/review/structural_quality_audit_2026-04-07.md](../review/structural_quality_audit_2026-04-07.md)
2. [docs/audit/structural_quality_backlog.md](structural_quality_backlog.md)
3. [AGENTS.md](../../AGENTS.md)

This should be enough to continue implementation without a second broad audit.