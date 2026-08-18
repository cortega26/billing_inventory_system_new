# Plan 035: Translate all user-facing strings to Spanish (incl. receipt PDF)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d560e43..HEAD -- services/receipt_service.py ui/sale_view_support.py ui/sale_view.py ui/sale_view_tables.py`
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code; on a mismatch treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `d560e43`, 2026-08-17
- **Issue**: —

## Why this matters

The repo contract (AGENTS.md: "New or modified UI strings must be in Spanish";
SPECIFICATIONS.md language decision 2026-08-15) requires a Spanish UI. Several
dialogs, error messages, button tooltips, and the ENTIRE PDF receipt body are
English. End users see mixed-language dialogs, and every receipt PDF shipped to
customers is in English. This is a user-visible contract violation with S-effort
fix.

## Current state

Verified locations (grep-confirmed at commit `d560e43`):

- `services/receipt_service.py:36-79` — the whole receipt body:
  `"Receipt #..."` (:36), `"Date: ..."` (:40), `"Customer ID: ..."` (:41),
  `"Product"` (:45), `"Quantity"` (:46), `"Price"` (:47), `"Total"` (:48),
  `"Product ID: ..."` (:56), `"Total:"` (:73), `"Profit:"` (:78).
- `ui/sale_view_support.py:119` — `"Please enter a 3/4-digit or 9-digit identifier"`.
- `ui/sale_view.py:848` — `"No customer found with the given identifier"`.
- `ui/sale_view.py:951` — `"Not Found"`, `"No products found matching the search term"`.
- `ui/sale_view.py:1157-1158` — `"Delete Sale"`, `"Are you sure you want to delete sale ..."`.
- `ui/sale_view.py:1226` — `"Save Receipt"`.
- `ui/sale_view_tables.py:137-140` — tooltips `"View sale details"`, `"Edit sale"`,
  `"Print receipt"`, `"Delete this sale"`.

**Repo conventions** (match these):
- Spanish wording already used elsewhere in the same screens: "Eliminar",
  "Guardar recibo", "Cliente", "Fecha", "Total", "Ganancia", "No Encontrado",
  "Error", "Seleccionar Producto" (see `ui/purchase_view.py:493`, `ui/sale_view_tables.py:115`).
- The `$` currency formatting (`f"${x:,}".replace(",", ".")`) is correct and
  stays; only the label text changes.

## Commands you will need

| Purpose   | Command | Expected on success |
|-----------|---------|---------------------|
| Receipt tests | `.venv/bin/python -m pytest tests/test_services/test_receipt_service.py tests/test_ui/test_sale_view_helpers.py tests/test_ui/test_sale_view_tables.py` | all pass |
| Sale UI tests | `.venv/bin/python -m pytest tests/test_ui/` | all pass (requires xvfb/display) |
| Full suite | `.venv/bin/python -m pytest` | all pass |
| Lint | `.venv/bin/ruff check .` | exit 0 |
| Format | `.venv/bin/black --check .` | exit 0 |

## Scope

**In scope**:
- `services/receipt_service.py` (receipt labels only — layout/format unchanged)
- `ui/sale_view_support.py`
- `ui/sale_view.py`
- `ui/sale_view_tables.py`
- `tests/` (only to update tests asserting the English strings)

**Out of scope**:
- Layout, fonts, or coordinates in `receipt_service.py`
- Money formatting logic (`format_price`)
- Any other English text found elsewhere (report it in the PR description instead of expanding scope)

## Git workflow

- Branch: `advisor/035-spanish-strings`
- Commit per logical unit (`fix: ...`, `tests: ...`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Translate the receipt PDF labels

In `services/receipt_service.py`, translate the `c.drawString` label strings.
Suggested wording (match existing UI style; you may adjust to natural Spanish):
- `"Receipt #"` → `"Recibo #"`
- `"Date:"` → `"Fecha:"`
- `"Customer ID:"` → `"ID Cliente:"`
- `"Product"` → `"Producto"`
- `"Quantity"` → `"Cantidad"`
- `"Price"` → `"Precio"`
- `"Total"` → `"Total"`
- `"Product ID:"` → `"ID Producto:"`
- `"Total:"` → `"Total:"`
- `"Profit:"` → `"Ganancia:"`
Do NOT change the `$`-formatting expressions or the layout coordinates.

**Verify**: `grep -n '"Receipt #"\|"Date:\|"Customer ID\|"Product"\|"Quantity"\|"Price"\|"Total"\|"Profit' services/receipt_service.py`
→ no English label literals remain (only Spanish). `.venv/bin/python -m pytest tests/test_services/test_receipt_service.py` → all pass.

### Step 2: Translate the UI strings

- `ui/sale_view_support.py:119` →
  `raise ValidationException("Ingrese un identificador de 3/4 o 9 dígitos")`
- `ui/sale_view.py:848` → `"No se encontró cliente con el identificador indicado"`
- `ui/sale_view.py:951` → title `"No Encontrado"`, message `"No se encontraron productos que coincidan con la búsqueda"`
- `ui/sale_view.py:1157-1158` → `"Eliminar Venta"` and
  `f"¿Está seguro que desea eliminar la venta {sale.receipt_id or sale.id}?\n"`
  (match the "¿Está seguro que desea ..." wording used in `ui/customer_view.py:444`)
- `ui/sale_view.py:1226` → `"Guardar Recibo"`
- `ui/sale_view_tables.py:137-140` → tooltips: `"Ver detalle de venta"`,
  `"Editar venta"`, `"Imprimir recibo"`, `"Eliminar venta"`

**Verify**: `grep -rn '"View sale\|"Edit sale\|"Print receipt\|"Delete this sale\|Delete Sale\|Are you sure\|Save Receipt\|No customer found\|No products found\|Please enter a 3' ui/`
→ no English matches in the in-scope files.

### Step 3: Update any tests asserting the English strings

Run `.venv/bin/python -m pytest tests/test_ui/ tests/test_services/test_receipt_service.py`
and update any assertion that pinned an English string to its Spanish
translation. Note each updated assertion in the commit message.

**Verify**: targeted test files pass.

### Step 4: Full verification

**Verify**: `.venv/bin/python -m pytest` → all pass; `.venv/bin/ruff check .`
→ exit 0; `.venv/bin/black --check .` → exit 0; `.venv/bin/pyright` → exit 0.

## Test plan

- No new tests required (string-only change). If the suite contains tests
  asserting the English text, update them to the Spanish text (Step 3).
- If no test covers the receipt text, optionally add a smoke assertion in
  `tests/test_services/test_receipt_service.py` that the generated PDF bytes
  contain the Spanish label "Recibo #" (pattern: generate to a tmp path and
  read the PDF's binary content with `pdfminer`-free string search on raw
  bytes; only add this if trivially feasible in the existing test file).

## Done criteria

- [ ] `.venv/bin/python -m pytest` exits 0
- [ ] `grep -rn '"Receipt #"\|"Date:\|"Customer ID\|"Product"\|"Quantity"\|"Price"\|"Profit' services/receipt_service.py ui/` returns no matches
- [ ] `grep -rn '"View sale\|"Edit sale\|"Print receipt\|"Delete this sale\|"Delete Sale"\|"Are you sure\|"Save Receipt"\|"No customer found\|"No products found\|"Please enter a 3' ui/` returns no matches
- [ ] `.venv/bin/ruff check .`, `.venv/bin/black --check .` exit 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A test asserts English receipt text that you cannot locate or update.
- The receipt test file expects byte-exact PDF output (unlikely; report if so).
- You find MORE than a handful of other English strings in the in-scope files —
  report them in the PR but do not expand scope beyond the listed locations
  without confirmation.

## Maintenance notes

- The receipt PDF is the highest-visibility surface: a reviewer should open a
  generated receipt and confirm labels are Spanish and alignment is unchanged.
- Future UI strings must be Spanish (repo contract). If `config.language`
  (currently a no-op key) is ever wired up, revisit this plan's hardcoded strings.