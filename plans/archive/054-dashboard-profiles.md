# Plan 054: Dashboard KPI profile via registry, not if/elif

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- ui/dashboard_view.py config.py tests/test_ui/test_dashboard_view.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

`DashboardView._metric_cards` decides which KPIs to show with an `if/elif` on a
config string; an unknown profile silently falls into the `else` branch
(dashboard_view.py:271-279). The allowed values live in a separate tuple in
`config.py` (`DASHBOARD_PROFILES`), so a third profile requires editing two
files in lockstep and a config value that passes validation but isn't handled
in the view renders a silent wrong dashboard. A registry makes the mapping
data, not control flow.

## Current state

- `ui/dashboard_view.py:262-279` — `_metric_cards`:
  ```python
  common = [MetricWidget("Ventas Totales", ...), ...]
  if profile == "production":
      return common + [MetricWidget("Unidades Vendidas", ...), MetricWidget("Ventas de Hoy", ...)]
  return common + [MetricWidget("Valor Inventario", ...), MetricWidget("Ventas de Hoy", ...)]
  ```
  (`profile` comes from `config.get_active_business().get("dashboard", DEFAULT_DASHBOARD_PROFILE)`.)
- `config.py:61-62` — `DASHBOARD_PROFILES = ("reseller", "production")`,
  validated in `_validate_businesses` (:260-265).

**Repo conventions**: config stays UI-free (no `config → ui` import). The
registry lives in the UI layer; `config.py` keeps its tuple as the validation
authority with a comment that it must match the UI registry keys.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Dashboard UI tests | `.venv/bin/python -m pytest tests/test_ui/test_dashboard_view.py tests/test_ui/test_main_window_helpers.py` | all pass (xvfb) |
| Config tests | `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py tests/test_services/test_business_switch.py` | all pass |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint / Format / Type | `.venv/bin/ruff check .`; `.venv/bin/black --check .`; `.venv/bin/pyright` | all exit 0 |

## Scope

**In scope**:
- `ui/dashboard_view.py`
- `config.py` (comment only)
- `tests/test_ui/test_dashboard_view.py`

**Out of scope**:
- The `MetricWidget` class
- The `get_total_*`/`get_todays_sales` metric getters (unchanged)

## Git workflow

- Branch: `advisor/054-dashboard-profiles`
- Commit per logical unit (`refactor: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Extract the profile registry

In `ui/dashboard_view.py`, add a module-level registry (placed near the class):

```python
def _production_metrics(view) -> list:
    return [
        MetricWidget("Unidades Vendidas", view.get_total_units_sold),
        MetricWidget("Ventas de Hoy", view.get_todays_sales),
    ]

def _reseller_metrics(view) -> list:
    return [
        MetricWidget("Valor Inventario", view.get_inventory_value),
        MetricWidget("Ventas de Hoy", view.get_todays_sales),
    ]

DASHBOARD_PROFILE_METRICS = {
    "production": _production_metrics,
    "reseller": _reseller_metrics,
}
```

Rewrite `_metric_cards` to look up the registry:

```python
def _metric_cards(self) -> list[MetricWidget]:
    profile = config.get_active_business().get("dashboard", DEFAULT_DASHBOARD_PROFILE)
    common = [
        MetricWidget("Ventas Totales", self.get_total_sales),
        MetricWidget("Ganancia Total", self.get_total_profits),
        MetricWidget("Margen Ganancia", self.get_profit_margin),
    ]
    builder = DASHBOARD_PROFILE_METRICS.get(profile)
    if builder is None:
        raise ValueError(f"Unknown dashboard profile: {profile!r}")
    return common + builder(self)
```

**Verify**: `.venv/bin/python -m pytest tests/test_ui/test_dashboard_view.py` → pass.

### Step 2: Annotate the config tuple

In `config.py:61`, add a comment: `# Must match DASHBOARD_PROFILE_METRICS keys in ui/dashboard_view.py`.

**Verify**: no behavior change; `.venv/bin/python -m pytest tests/test_config.py tests/test_system/test_config.py` → pass.

### Step 3: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- Existing dashboard tests cover both profiles; add one assertion test that
  `_metric_cards` raises on an unknown profile if one does not already exist
  (mock `config.get_active_business` to return an unknown dashboard value).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -n "if profile ==" ui/dashboard_view.py` returns no matches
- [ ] Unknown-profile test exists and passes
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .`, `.venv/bin/pyright` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A dashboard UI test asserts the silent-else fallback for unknown profiles
  (the new code raises by design — update the test to assert the raise).
- `config` is imported by `dashboard_view.py` only for `get_active_business`
  (it already is — no new dependency introduced).

## Maintenance notes

- Adding a profile = one registry entry in `dashboard_view.py` + one tuple
  entry in `config.py`. The `ValueError` makes a mismatch loud instead of
  silent.
- The `get_*` getters are unchanged; profiles only compose them.