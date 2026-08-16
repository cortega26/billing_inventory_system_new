# Plan 027: Per-business dashboard KPI profiles (reseller vs production)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat cb0a8f5..HEAD -- config.py ui/dashboard_view.py services/sale_service.py tests/test_system/test_config.py tests/test_config.py tests/test_services/test_sale_service.py tests/test_ui/ SPECIFICATIONS.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2 (UX/product — requested for casabea.cl)
- **Effort**: S-M
- **Risk**: LOW (card composition + one new read-only service method)
- **Depends on**: none
- **Category**: feature
- **Planned at**: commit `cb0a8f5`, 2026-08-16

## Why this matters

The dashboard shows the same five KPI cards for every business
(`ui/dashboard_view.py:97-105`): Ventas Totales, Ganancia Total, **Valor
Inventario**, Margen Ganancia, Ventas de Hoy. For a reseller (El Rincón de
Ébano) inventory value is working capital and belongs front and center; for a
value-added producer (casabea.cl, cinnamon rolls) the inputs are cheap and
consumed fast — the meaningful signals are **margin %** and **units sold**,
not inventory value. The per-business registry (plan 022) is the natural seam
for a per-business KPI profile. "Valor agregado" needs no new economic
metric — Ganancia Total already equals revenue − ingredient cost; the profile
just changes which cards lead.

## Current state

```python
# ui/dashboard_view.py:96-106 — the fixed card row
metrics_layout = QHBoxLayout()
metrics_layout.addWidget(MetricWidget("Ventas Totales", self.get_total_sales))
metrics_layout.addWidget(MetricWidget("Ganancia Total", self.get_total_profits))
metrics_layout.addWidget(MetricWidget("Valor Inventario", self.get_inventory_value))
metrics_layout.addWidget(MetricWidget("Margen Ganancia", self.get_profit_margin))
metrics_layout.addWidget(MetricWidget("Ventas de Hoy", self.get_todays_sales))
layout.addLayout(metrics_layout)
# MetricWidget(label, value_func) at dashboard_view.py:38 — a plain card frame.
```

The totals cards use a selectable range (`self.start_date`/`self.end_date`,
formatted `%Y-%m-%d`), see `get_total_sales`/`get_total_profits` at
`dashboard_view.py:237-250`:

```python
total_sales_value = self.sale_service.get_total_sales(
    self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
)
```

The registry lives in `config.py` (plan 022): `DEFAULT_BUSINESSES`
(`config.py:59-63`), `_validate_businesses` (`config.py:210-246` — validates
id/name/db_filename), `get_active_business()` returns the active entry dict.
Plan 025 made the registry always present (self-healing defaults), and the
user-facing config currently has entries for `default` and `casabea`.

There is NO units-total method anywhere (verified: only per-product
`sales_volume`/`units_sold` inside analytics metrics); `get_total_units_sold`
must be added to `SaleService` mirroring `get_total_sales`
(`services/sale_service.py:345-363`), including the `status = 'confirmed'`
filter (plan 015) and `validate_date` bounds.

Repo conventions that apply:

- User-facing strings in Spanish (card labels stay Spanish).
- New public methods need a caller or a test (AGENTS.md dead-code rule) —
  the dashboard card is the caller; add a service test too.
- UI tests: `tests/test_ui/` under `xvfb-run`, `qtbot`/`qapp` fixtures,
  `db_manager` real-DB fixture. There is NO dashboard test file yet — create
  `tests/test_database`-style... i.e. `tests/test_ui/test_dashboard_view.py`
  (follow `tests/test_ui/test_business_selector_dialog.py` for the qtbot +
  real-DB pattern).
- Config changes: `tests/test_config.py` + `tests/test_system/test_config.py`
  updated together.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Config tests | `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` | all pass |
| Sale tests | `.venv/bin/python -m pytest tests/test_services/test_sale_service.py` | all pass |
| New UI tests | `xvfb-run -a .venv/bin/python -m pytest tests/test_ui/test_dashboard_view.py` | all pass |
| UI suite | `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |
| Type check | `.venv/bin/pyright` | exit 0 |

## Scope

**In scope**:
- `config.py` — `dashboard` field: validation whitelist in `_validate_businesses`, add to `DEFAULT_BUSINESSES` entries
- `services/sale_service.py` — `get_total_units_sold(start_date, end_date)` (read-only; mirrors `get_total_sales`)
- `ui/dashboard_view.py` — profile-based card row + `get_total_units_sold` card method
- `tests/test_system/test_config.py` (+ `tests/test_config.py` if needed) — registry `dashboard` validation
- `tests/test_services/test_sale_service.py` — units-sold tests
- `tests/test_ui/test_dashboard_view.py` — NEW profile-render tests
- `SPECIFICATIONS.md` — dashboard-profiles section

**Out of scope** (do NOT touch):
- Charts and the low-stock alert — identical for both profiles
- Analytics metrics/engine — no new metrics (Ganancia Total already captures value added)
- Per-card user customization (show/hide/reorder in the UI) — future work, not this plan
- Anything in `services/` beyond the one new read-only method

## Git workflow

- Branch: `advisor/027-dashboard-profiles`
- Commit per step; message style follows the repo (`feat: ...`, `tests: ...`, `docs: ...`)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Registry field

In `config.py`:

1. Add a module-level constant next to `DEFAULT_BUSINESSES`:
   ```python
   DASHBOARD_PROFILES = ("reseller", "production")
   DEFAULT_DASHBOARD_PROFILE = "reseller"
   ```
2. `DEFAULT_BUSINESSES` entries gain `"dashboard": DEFAULT_DASHBOARD_PROFILE`.
3. In `_validate_businesses` (config.py:210-246): each business may carry
   `dashboard`; when present it must be in `DASHBOARD_PROFILES`, else raise
   `ConfigValidationError` (mirror the existing error style). Missing field
   is allowed (defaults to reseller at the point of use).

**Verify**: `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` → all pass (add Step 4's validation tests now or in Step 4; either order).

### Step 2: The units-sold service method

In `services/sale_service.py`, add a static method mirroring
`get_total_sales` (same decorators, validation, and `status='confirmed'`):

```python
@staticmethod
@db_operation(show_dialog=True)
@handle_exceptions(DatabaseException, show_dialog=True)
def get_total_units_sold(start_date: str, end_date: str) -> float:
    start_date = validate_date(start_date)
    end_date = validate_date(end_date)
    query = """
        SELECT COALESCE(ROUND(SUM(si.quantity), 3), 0) as total_units
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.date BETWEEN ? AND ? AND s.status = 'confirmed'
    """
    result = DatabaseManager.fetch_one(query, (start_date, end_date))
    total_units = float(result["total_units"] if result else 0)
    logger.info("Total units sold retrieved", extra={
        "start_date": start_date, "end_date": end_date, "total_units": total_units,
    })
    return total_units
```

**Verify**: `.venv/bin/python -m pytest tests/test_services/test_sale_service.py` → all pass.

### Step 3: Profile-based dashboard cards

In `ui/dashboard_view.py`:

1. Add the units card method next to `get_todays_sales`:
   ```python
   @ui_operation()
   def get_total_units_sold(self) -> str:
       units = self.sale_service.get_total_units_sold(
           self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
       )
       return f"{units:,.3f}".replace(",", ".").rstrip("0").rstrip(".")
   ```
2. Extract the card-row construction into a profile-aware helper and use it
   in `setup_ui` (lines 96-106):
   ```python
   def _metric_cards(self) -> list[MetricWidget]:
       profile = config.get_active_business().get(
           "dashboard", DEFAULT_DASHBOARD_PROFILE
       )
       common = [
           MetricWidget("Ventas Totales", self.get_total_sales),
           MetricWidget("Ganancia Total", self.get_total_profits),
           MetricWidget("Margen Ganancia", self.get_profit_margin),
       ]
       if profile == "production":
           return common + [
               MetricWidget("Unidades Vendidas", self.get_total_units_sold),
               MetricWidget("Ventas de Hoy", self.get_todays_sales),
           ]
       return common + [
           MetricWidget("Valor Inventario", self.get_inventory_value),
           MetricWidget("Ventas de Hoy", self.get_todays_sales),
       ]
   ```
   (`setup_ui` replaces the five addWidget calls with a loop over
   `self._metric_cards()`; import `DEFAULT_DASHBOARD_PROFILE` from `config`
   — check what `dashboard_view.py` already imports from config.)
3. Import `config`/`DEFAULT_DASHBOARD_PROFILE` at the top of the file (the
   file already imports `from config import config` inside
   `update_backup_status` at line 287 — prefer a top-level import now).

**Verify**: `xvfb-run -a .venv/bin/python -m pytest tests/test_ui` → all pass (modulo the known worktree quirk file).

### Step 4: Tests

1. Config (`tests/test_system/test_config.py`, following the existing
   registry-validation tests):
   - `test_business_dashboard_profile_invalid_rejected` — registry entry with
     `"dashboard": "foo"` raises `ConfigValidationError`.
   - `test_business_dashboard_profile_defaults_to_reseller` — entry without
     `dashboard` loads; `get_active_business().get("dashboard")` is
     `"reseller"` (assert via the profile-aware helper's default path).
2. Sale service (`tests/test_services/test_sale_service.py`, mirroring the
   existing `test_get_total_sales_excludes_cancelled_sales` pattern from plan
   015):
   - `test_get_total_units_sold_sums_confirmed_sales` — seed inventory +
     sale with quantity 2.5, assert 2.5.
   - `test_get_total_units_sold_excludes_cancelled_sales` — create + cancel,
     assert 0.
3. Dashboard UI — NEW `tests/test_ui/test_dashboard_view.py` (follow
   `tests/test_ui/test_business_selector_dialog.py` for the qtbot +
   `db_manager` pattern):
   - `test_reseller_profile_shows_inventory_value_card` — config with
     `dashboard: reseller`, build `DashboardView`, assert a widget labeled
     "Valor Inventario" exists and "Unidades Vendidas" does not.
   - `test_production_profile_shows_units_card` — `dashboard: production`,
     assert "Unidades Vendidas" present and "Valor Inventario" absent.
   - Locate the dashboard's labels in the widget tree (the `MetricWidget`s
     are QFrames with labels — follow whatever introspection the existing UI
     tests use, e.g. `findChildren(QLabel)` and check `.text()`).
   - NOTE: `DashboardView` constructor may run queries against the DB —
     provide the `db_manager` fixture and seed minimal data if required; the
     profile assertions must not depend on query results.

**Verify**:
- `.venv/bin/python -m pytest tests/test_system/test_config.py tests/test_services/test_sale_service.py` → all pass
- `xvfb-run -a .venv/bin/python -m pytest tests/test_ui/test_dashboard_view.py` → 2 passed

### Step 5: Docs + full verification

1. `SPECIFICATIONS.md`: in the multi-business section add:
   "Dashboard por negocio: perfil `reseller` (incluye Valor Inventario) o
   `production` (incluye Unidades Vendidas), configurable por negocio en el
   registro; defecto: `reseller`."
2. **Verify**:
   - `.venv/bin/python -m pytest` → all pass (modulo pre-existing worktree UI exceptions in `tests/test_ui/test_main_window_helpers.py` — 7 known; plus the 4 backup tests that need the live DB file in the tree — pre-existing)
   - `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` → clean

## Test plan

| Test | File | Case |
|------|------|------|
| invalid dashboard profile rejected | test_system/test_config.py | `"dashboard": "foo"` → ConfigValidationError |
| missing profile defaults to reseller | test_system/test_config.py | `.get("dashboard")` → "reseller" |
| units sold sums confirmed sales | test_sale_service.py | seeded sale qty 2.5 → 2.5 |
| units sold excludes cancelled | test_sale_service.py | cancelled → 0 |
| reseller cards | test_dashboard_view.py | Valor Inventario present, Unidades Vendidas absent |
| production cards | test_dashboard_view.py | Unidades Vendidas present, Valor Inventario absent |

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `DASHBOARD_PROFILES = ("reseller", "production")` in `config.py`; `_validate_businesses` rejects unknown values
- [ ] `sale_service.get_total_units_sold` exists with the confirmed-status filter (grep `services/sale_service.py`)
- [ ] `ui/dashboard_view.py` composes the card row from `_metric_cards()` keyed on the active business's `dashboard` profile
- [ ] `tests/test_ui/test_dashboard_view.py` exists with the 2 profile tests
- [ ] `.venv/bin/python -m pytest` exits 0 (modulo pre-existing worktree UI exceptions)
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated (SKIP — reviewer maintains the index)

## STOP conditions

Stop and report back (do not improvise) if:

- `DashboardView.__init__` performs side effects that make the profile tests
  impractical with the `db_manager` fixture (report what it does instead of
  mocking it away).
- `get_total_sales`'s shape differs from the excerpt (report; the units
  method must mirror it exactly).
- A step's verification fails twice after a reasonable fix attempt.
- You're tempted to touch analytics/engine, charts, or the low-stock block —
  STOP instead.

## Maintenance notes

- The card composition is the single place that knows profiles; adding a
  third profile (e.g. `"wholesale"`) is one branch in `_metric_cards` + one
  whitelist entry.
- Per-card user customization (show/hide/reorder) is the natural next step
  and should reuse `_metric_cards`.
- Reviewer scrutiny: the units formatting (no `$`, trimmed decimals), the
  `status='confirmed'` filter, and that reseller behavior is byte-identical
  to today (same five cards, same order).
