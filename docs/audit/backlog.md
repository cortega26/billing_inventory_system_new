# Technical Audit Backlog
> Audited: 2026-04-06 | Auditor: Staff/Principal SE review via Claude
> System: Billing & Inventory (Python/SQLite/PySide6) | Currency: CLP integers only

---

## How to use this backlog

Each item includes:
- **File + line** — exact location
- **What to change** — concrete instruction, not abstract advice
- **Why** — business/technical justification
- **Phase** — implementation order dependency

Start a new conversation per phase: *"Implement Phase 0 of docs/audit/backlog.md"*

---

## PHASE 0 — Quick wins (no regression risk, 1–3 days) ✅ DONE 2026-04-06

### [C-1] ✅ Remove 1,000,000 CLP cap from line totals and sale/purchase totals
- **Files:**
  - `utils/validation/validators.py` — `validate_money()` line 190, `validate_money_multiplication()` line 222
  - `models/sale.py` — `recalculate_total()` lines 161–169
  - `models/purchase.py` — `recalculate_total()` lines 130–137, `add_item()` line 115
- **What to change:**
  - In `validate_money`: keep the cap ONLY for individual unit prices. Rename to `validate_unit_price()` or add a `max_value` parameter with `None` as default.
  - In `validate_money_multiplication`: remove the `validate_money` call on the result. The result is a line total, not a unit price. Just return `int(round(float(amount) * quantity))`.
  - In `Sale.recalculate_total()` and `Purchase.recalculate_total()`: call `validate_money(total, ...)` only to check it is an integer >= 0, not to cap at 1M.
  - `validate_money` should remain as the validator for **unit prices only** (used in `ProductService._validate_product_data`).
- **Why:** A product at $600,000 CLP sold in qty=2 produces a line total of $1,200,000 CLP — a perfectly valid commercial transaction that currently throws a ValidationException.
- **Implemented:** Added `max_value: Optional[int] = 1_000_000` param to `validate_money` (backward compatible); `validate_money_multiplication` now returns `int(round(float(amount) * quantity))` directly; `recalculate_total` in both models passes `max_value=None`.

---

### [C-2] ✅ Make `adjust_inventory` atomic
- **File:** `services/inventory_service.py` lines 253–278
- **Why:** If the process crashes between the stock update and the audit record insertion, inventory is modified with no traceable record.
- **Implemented:** Both `update_quantity` and the `INSERT INTO inventory_adjustments` are now wrapped in a single `with DatabaseManager.transaction()` block. Cache clear and event emit happen after the `with` block.

---

### [C-4] ✅ Fix `Inventory.create_empty()` and `Category.create_empty()` — id=-1 always throws
- **Files:**
  - `models/inventory.py` — `create_empty` default changed from `id=-1` to `id=0`
  - `models/category.py` — `create_empty` default changed from `id=-1` to `id=0`
- **Why:** `id=-1` fails the `id < 0` check. Both factory methods always threw, making them dead APIs.
- **Note:** `Category.create_empty()` also passes `name=""` which still fails `validate_name`; this additional issue is not in Phase 0 scope.

---

### [C-5] ✅ Remove duplicate `@staticmethod` from `get_all_sales`
- **File:** `services/sale_service.py`
- **Implemented:** Removed the second `@staticmethod` decorator above `def get_all_sales`.
- **Why:** Double decorator is a Python bug with undefined behavior across versions.

---

### [C-6-init] ✅ Raise exception when `schema.sql` not found in `init_db`
- **File:** `database/__init__.py`
- **Implemented:** Replaced `pass` with `raise DatabaseException(f"schema.sql not found. Expected at: {os.path.abspath(schema_path)}")`.
- **Why:** If the app is run from the wrong CWD, the database is initialized empty. All subsequent operations fail with confusing "no such table" errors instead of a clear startup failure.

---

### [A-7-p0] ✅ Fix `fix_invalid_sales` — revert stock before deleting sales
- **File:** `utils/validation/data_validator.py`
- **Implemented:** Rewrote `fix_invalid_sales` to:
  1. Fetch `sale_items` for all invalid sales before deletion.
  2. Call `InventoryService.apply_batch_updates(items, multiplier=1.0, emit_events=False)` inside a single `DatabaseManager.transaction()` block.
  3. Delete `sale_items`, then `sales` within the same transaction.
  4. Clear inventory cache after commit.
  Also removed unused `sqlite3` import patterns that used raw `conn.execute`.
- **Why:** Previously, future-dated sales were deleted but inventory was never restored — stock was permanently wrong.

---

## PHASE 1 — Integrity and correctness ✅ DONE 2026-04-06

### [A-1] ✅ Calculate `profit` server-side in `create_sale` and `update_sale`
- **File:** `services/sale_service.py`
  - `create_sale` lines 43–108: line 56 `total_profit = sum(int(item["profit"]) for item in items)`
  - `update_sale` lines 252–306: lines 284–289
- **What to change:**
  - In `_validate_sale_items`, fetch each product and compute `profit` server-side using `FinancialCalculator.calculate_item_profit(quantity, sell_price, product.cost_price)`.
  - Store the server-calculated profit, ignoring any `profit` sent by the caller.
  - This requires that `_validate_sale_items` receives access to `ProductService` (already available via `self.product_service`).
- **Why:** Client-supplied profit can be incorrect due to UI bugs or data corruption. The server must be the source of truth for financial figures.
- **Implemented:** `_validate_sale_items` now fetches each product via `self.product_service` and overwrites `item["profit"]` using `FinancialCalculator.calculate_item_profit`. `update_sale` simplified to sum the pre-computed values — the redundant product-fetch loop removed.

---

### [A-2] ✅ Remove silent `cost_price` update from `_insert_purchase_items`
- **File:** `services/purchase_service.py` lines 247–251
- **What to change:** Delete these two lines entirely:
  ```python
  update_query = "UPDATE products SET cost_price = ? WHERE id = ?"
  DatabaseManager.execute_query(update_query, (item["cost_price"], item["product_id"]))
  ```
- **Why:** Silently overwriting the current `cost_price` retroactively corrupts all historical profit analytics. Analytics queries JOIN `products.cost_price`, meaning every past sale recalculates profit with the new cost price.
- **Dependency:** Before removing, confirm the UI does not rely on this side effect to display updated cost prices. If it does, add an explicit "update cost price" button/workflow.
- **Implemented:** Deleted the two `UPDATE products SET cost_price` lines from `_insert_purchase_items`.

---

### [A-3] ✅ Add UNIQUE constraint to `sales.receipt_id`
- **File:** `schema.sql` line 51 and `database/migrations.py`
- **What to change:**
  - In `schema.sql`: change `receipt_id TEXT` to `receipt_id TEXT UNIQUE`
  - In `migrations.py` `add_performance_indexes()`: add `"CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_receipt_id ON sales(receipt_id) WHERE receipt_id IS NOT NULL"`
- **Why:** Receipt ID uniqueness is currently enforced only by application-level logic (SELECT MAX + increment under RLock). A DB-level constraint is the only reliable guarantee.
- **Implemented:** `schema.sql` — `receipt_id TEXT UNIQUE`. `migrations.py` — added `CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_receipt_id ON sales(receipt_id) WHERE receipt_id IS NOT NULL`.

---

### [A-4] ✅ Enforce integer type for prices in `Product.validate()`
- **File:** `models/product.py` lines 32–47
- **What to change:** Add at the start of `validate()`:
  ```python
  if not isinstance(self.cost_price, int) or isinstance(self.cost_price, bool):
      raise ValidationException("cost_price must be an integer (CLP, no decimals)")
  if not isinstance(self.sell_price, int) or isinstance(self.sell_price, bool):
      raise ValidationException("sell_price must be an integer (CLP, no decimals)")
  ```
- **Also fix:** `tests/test_models/test_product.py` — change `cost_price=1000.0` to `cost_price=1000` and `sell_price=1500.0` to `sell_price=1500` throughout the test file.
- **Why:** `Product(cost_price=1500.5)` currently passes validation, silently breaking the CLP-integer invariant.
- **Implemented:** Integer+bool checks added at top of `Product.validate()`. Test file updated: float literals → int literals throughout; added `test_float_price_rejected` test.

---

### [A-5] ✅ Allow negative profit in `Sale.recalculate_total()`
- **File:** `models/sale.py` lines 161–169
- **What to change:** Replace `validate_money(self.total_profit, "Total profit")` with a simple integer check:
  ```python
  if not isinstance(self.total_profit, int):
      raise ValidationException("Total profit must be an integer")
  # profit can legitimately be negative (selling below cost)
  ```
- **Why:** Selling below cost (clearance, pricing error corrections) is a valid business scenario. `validate_money` rejects negative values, crashing the domain model on legitimate sales.
- **Implemented:** Replaced `validate_money(self.total_profit, ...)` with a plain `isinstance(self.total_profit, int)` check. Negative profits now accepted.

---

### [A-6] ✅ Fix `validate_string` to accept Spanish characters
- **File:** `utils/validation/validators.py` lines 86–91
- **What to change:** Replace the character whitelist check with one that supports Spanish:
  ```python
  # BEFORE
  if not all(c.isalnum() or c.isspace() or c in "-." for c in value):
      raise ValidationException("Value contains invalid characters")

  # AFTER — allow alphanumeric (incl. Unicode/Spanish), spaces, and common punctuation
  allowed_extra = set("-.,;:()'/&%#+")
  if not all(c.isalpha() or c.isdigit() or c.isspace() or c in allowed_extra for c in value):
      raise ValidationException("Value contains invalid characters")
  ```
  Note: `c.isalpha()` in Python 3 returns True for `ñ`, `á`, `é`, etc.
- **Why:** Supplier names like "Distribuidora García & Cía." and product names like "Aceite 1/4 Lt (500ml)" are currently rejected.
- **Implemented:** Replaced `c.isalnum() or c in "-."` check with `c.isalpha() or c.isdigit() or c.isspace() or c in allowed_extra` where `allowed_extra = set("-.,;:()'/&%#+")`.

---

### [A-7] ✅ Fix `get_purchase_statistics` — null check on row
- **File:** `services/purchase_service.py` lines 426–441
- **What to change:**
  ```python
  row = DatabaseManager.fetch_one(query, (start_date, end_date))
  if not row:
      return {
          "total_purchases": 0,
          "total_amount": 0,
          "suppliers": PurchaseService.get_suppliers(),
      }
  return {
      "total_purchases": row["total_purchases"],
      "total_amount": row["total_amount"],
      "suppliers": PurchaseService.get_suppliers(),
  }
  ```
- **Also:** Add `validate_date(start_date)` and `validate_date(end_date)` at the start of this method (currently missing).
- **Implemented:** Added `validate_date` calls at method start; replaced direct row access with `if not row` guard returning zero defaults.

---

### [A-8] ✅ Migrate `ProductService.create_product` to use `with DatabaseManager.transaction()`
- **File:** `services/product_service.py` lines 37–87
- **What to change:** Replace the manual `begin_transaction()`/`commit_transaction()`/`rollback_transaction()` calls with the `with DatabaseManager.transaction():` context manager. The event emission should happen AFTER the `with` block exits successfully.
- **Why:** The current code can call `rollback_transaction()` on an already-committed transaction, and the `except` block handles events and transaction state inconsistently.
- **Implemented:** Replaced `begin_transaction/commit_transaction/rollback_transaction` calls with `with DatabaseManager.transaction():`. Cache clear and event emission moved after the `with` block.

---

### [A-9] ✅ Fix analytics SQL — use `CAST(ROUND(...) AS INTEGER)`
- **File:** `services/analytics_service.py`
- **What to change:** In every query that computes a monetary aggregate, replace:
  - `SUM(ROUND(si.quantity * si.price))` → `CAST(SUM(ROUND(si.quantity * si.price)) AS INTEGER)`
  - `SUM(ROUND(si.quantity * (si.price - p.cost_price)))` → `CAST(SUM(ROUND(si.quantity * (si.price - p.cost_price))) AS INTEGER)`
  - Affected methods: `get_top_selling_products`, `get_profit_and_volume_by_product`, `get_category_performance`, `get_profit_by_product`, `get_profit_margin_distribution`
- **Why:** SQLite `ROUND()` returns REAL (float). CLP values must be integers. Tests already confirm the float leak (`assert isinstance(..., float)`).
- **Implemented:** All 5 affected methods updated. `get_profit_margin_distribution` subquery inner `SUM(ROUND(...))` expressions also wrapped with `CAST(... AS INTEGER)`.

---

### [A-10] ✅ Validate `start_date <= end_date` in all analytics methods
- **File:** `services/analytics_service.py`
- **What to change:** The private `_validate_date_range()` method at line 352 already implements this logic. Call it in every public method after `validate_date()` calls:
  ```python
  start_date = validate_date(start_date)
  end_date = validate_date(end_date)
  self._validate_date_range(start_date, end_date)  # ADD THIS
  ```
  Change `_validate_date_range` from an instance method to a `@staticmethod` so it can be called from static methods.
- **Affected methods:** All 9 `@lru_cache` analytics methods and `get_sales_summary`.
- **Implemented:** `_validate_date_range` converted to `@staticmethod`. Called as `AnalyticsService._validate_date_range(start_date, end_date)` in all 10 public methods after `validate_date` calls.

---

## PHASE 2 — Robustness and maintainability ✅ DONE 2026-04-06

### [M-1] ✅ Add `status` column to `sales` table
- **Files:** `schema.sql`, `database/migrations.py`, `models/sale.py`, `services/sale_service.py`
- **Implemented:**
  - `schema.sql`: Added `status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled'))` and `created_at TEXT NOT NULL DEFAULT (datetime('now'))` to `sales`.
  - `migrations.py`: Added `add_schema_columns()` which runs `ALTER TABLE sales ADD COLUMN status ...` (and the other M-2 columns) idempotently — ignores "duplicate column name" errors.
  - `models/sale.py`: Added `status: str = 'confirmed'` field, `VALID_STATUSES` constant, `validate_status()` static method; `from_db_row` reads `status` with fallback to `'confirmed'`; `to_dict` includes `status`.
  - `services/sale_service.py`: Added `cancel_sale(sale_id)` — validates not already cancelled, reverts inventory and sets `status='cancelled'` in a single transaction, emits `sale_updated` event.
- **Why:** Soft-cancel preserves the audit trail. Previously the only way to void a sale was to delete it.

---

### [M-2] ✅ Add `created_at` timestamps to sales and purchases
- **Files:** `schema.sql`, `database/migrations.py`
- **Implemented:** Added `created_at TEXT NOT NULL DEFAULT (datetime('now'))` to `sales`, `sale_items`, and `purchases` in both `schema.sql` (for new DBs) and `migrations.py` `add_schema_columns()` (for existing DBs).

---

### [M-3] ✅ Fix `get_sale_items` — do not swallow exceptions silently
- **File:** `services/sale_service.py`
- **Implemented:** Removed the bare `except` block around `SaleItem.from_db_row(row)`. Exceptions now propagate so callers know when a sale item cannot be parsed.

---

### [M-4] ✅ Sync `Inventory` model with schema (Option A)
- **File:** `models/inventory.py`
- **Implemented:** Removed `min_stock_level`, `max_stock_level`, `reorder_point`, `reorder_quantity` fields from the dataclass. Removed dependent methods `set_stock_levels`, `needs_reorder`, `get_suggested_order_quantity`. Simplified `get_stock_status` to OUT_OF_STOCK vs OPTIMAL. `update_quantity` and `set_quantity` no longer check `max_stock_level`. Confirmed no external code referenced these fields.

---

### [M-5] ✅ Register `set_quantity` changes in `inventory_adjustments`
- **File:** `services/inventory_service.py`
- **Implemented:** `set_quantity` now fetches the current quantity, computes the delta, and wraps `_modify_inventory` + `INSERT INTO inventory_adjustments (reason='manual_set')` in a single `DatabaseManager.transaction()`. Cache clear and event emit happen after the `with` block.

---

### [M-6] ✅ Fix `conftest.py` — remove references to nonexistent tables
- **File:** `tests/conftest.py`
- **Implemented:** Removed `"users"` and `"suppliers"` from the `tables` list in `clear_test_data`. `Config` class exists in `config.py` — `isolate_config` fixture is valid as-is.

---

### [M-7] ✅ Fix `Category.NAME_PATTERN` — missing end anchor `$`
- **File:** `models/category.py` line 30
- **Implemented:** `NAME_PATTERN` already had `$` from a prior edit. No change needed.

---

## PHASE 3 — Scalability and evolution ✅ DONE 2026-04-06

### [S-1] ✅ Paginate `get_all_sales` and `get_sales_by_date_range`
- **Files:** `services/sale_service.py`
- **Implemented:**
  - `get_all_sales(limit: int = 100, offset: int = 0)` — SQL-level `LIMIT ? OFFSET ?`. Items fetched only for the current page via `WHERE si.sale_id IN (...)`. `@lru_cache` bumped to `maxsize=128` to cache multiple page combinations.
  - `get_sales_by_date_range(…, limit: int = 100, offset: int = 0)` — same pagination added. Switched from N+1 `get_sale_items` loop to a single batch items query using the same IN-clause pattern.

### [S-2] ✅ Eliminate N+1 in `get_all_purchases`
- **File:** `services/purchase_service.py`
- **Implemented:** Replaced the per-purchase `get_purchase_items(purchase.id)` loop with a single `SELECT * FROM purchase_items WHERE purchase_id IN (...)` query. Items grouped by `purchase_id` in Python and assigned in bulk.

### [S-3] ✅ Fix `get_inventory_turnover` — AVG(quantity) is meaningless on a static table
- **File:** `services/inventory_service.py`
- **Implemented:** Removed the `avg_inventory` CTE entirely. Now JOINs `inventory` directly and uses `i.quantity` as the denominator (`total_sold / i.quantity`). Also changed date parameter validation from `validate_string` to `validate_date` (added `validate_date` to the module imports).

### [S-4] ✅ Store `quantity_change` in `inventory_adjustments` as REAL, not TEXT
- **File:** `services/inventory_service.py` — `adjust_inventory`
- **Implemented:** Removed `str(quantity_change)` wrapper; the value is now passed directly as a Python `float`, matching the `DECIMAL(10,3)` column type.

---

## PHASE 4 — Cache correctness, validation completeness, test coverage ✅ DONE 2026-04-06

### [P4-1] ✅ Invalidate analytics cache after sale/purchase mutations
- **Files:** `services/sale_service.py` — `_finalize_sale_mutation`; `services/purchase_service.py` — `_finalize_purchase_mutation`
- **What to change:** Add `AnalyticsService.clear_cache()` call in both finalize methods, after `InventoryService.clear_cache()`.
- **Why:** `AnalyticsService` has a `clear_cache()` method and all its methods are `@lru_cache`, but it was never called after mutations. Dashboard charts showed stale data for the entire session after any sale or purchase was created, updated, or deleted.
- **Implemented:** Added `AnalyticsService.clear_cache()` to both `_finalize_sale_mutation` (sale_service.py) and `_finalize_purchase_mutation` (purchase_service.py). Also added `from services.analytics_service import AnalyticsService` import to both files.

---

### [P4-2] ✅ Validate `multiplier` in `InventoryService.apply_batch_updates`
- **File:** `services/inventory_service.py` — `apply_batch_updates`
- **What to change:** Add guard at the start of the method: `if multiplier not in (1.0, -1.0): raise ValidationException(...)`.
- **Why:** Any caller passing `multiplier=0.5` or `multiplier=2.0` would silently corrupt inventory. The parameter only has two valid values and this should be enforced.
- **Implemented:** Guard added before the item loop.

---

### [P4-3] ✅ Add input validation to `get_supplier_purchases` and `get_purchase_history`
- **File:** `services/purchase_service.py`
- **What to change:**
  - `get_supplier_purchases`: add `supplier = validate_string(supplier, min_length=1, max_length=100)`.
  - `get_purchase_history`: add `validate_date` calls for both dates + `start_date > end_date` check.
- **Why:** Both methods accepted raw, unvalidated strings directly into SQL queries. Invalid input would return empty results silently or produce unexpected behavior.
- **Implemented:** Both methods now validate their inputs. `get_purchase_history` also raises `ValidationException` if `start_date > end_date`.

---

### [P4-4] ✅ Remove dead code `if not sale:` in `cancel_sale`
- **File:** `services/sale_service.py` — `cancel_sale` lines 269–271
- **What to change:** Delete the `if not sale: raise NotFoundException(...)` block.
- **Why:** `self.get_sale(sale_id)` already raises `NotFoundException` if the sale doesn't exist. The null check immediately after can never execute and misleads future readers about the control flow.
- **Implemented:** Dead code removed.

---

### [P4-5] ✅ Fix `get_inventory_movements` to use `validate_date` + start ≤ end check
- **File:** `services/inventory_service.py` — `get_inventory_movements` lines 307–308
- **What to change:** Replace `validate_string(start_date)` / `validate_string(end_date)` with `validate_date(...)`. Add `if start_date > end_date: raise ValidationException(...)`.
- **Why:** `validate_string` accepts any non-empty string — an invalid date like `"not-a-date"` would pass silently and return empty results from the BETWEEN clause instead of a clear error.
- **Implemented:** Both parameters now use `validate_date`. Range check added.

---

### [P4-6] ✅ Guard receipt ID counter overflow in `_build_receipt_id`
- **File:** `services/sale_service.py` — `_build_receipt_id`
- **What to change:** After computing `next_number = last_number + 1`, raise `ValidationException` if `next_number > 999`.
- **Why:** The format string `f"{date_part}{next_number:03d}"` produces a 9-character ID for counters 001–999. Counter 1000 produces a 10-character ID, breaking the format and potentially causing duplicate IDs (e.g., `260406001` clashes with `2604060` + `01`).
- **Implemented:** Guard added; raises `ValidationException("Daily receipt limit reached for {date} (max 999 per day)")`.

---

### [P4-7] ✅ Add `max_value=1000` to `limit` parameters in reporting methods
- **Files:** `services/sale_service.py` — `get_top_selling_products`; `services/analytics_service.py` — `get_top_selling_products`, `get_profit_by_product`; `services/purchase_service.py` — `get_top_suppliers`
- **What to change:** All `validate_integer(limit, min_value=1)` calls in reporting methods should add `max_value=1000`.
- **Why:** An unbounded `limit` (e.g., `limit=999999999`) causes the query to load the entire table into memory, causing app hangs or OOM errors.
- **Implemented:** `max_value=1000` added to all four methods.

---

### [P4-8] ✅ Add missing test coverage and fix pre-existing test breakage
- **Files:** `tests/test_services/test_sale_service.py`, `tests/test_services/test_product_service.py`
- **What to change:**
  - `test_sale_service.py`: Add `TestCancelSale` class (5 tests: sets status, reverts inventory, raises on double cancel, raises on nonexistent ID, preserves audit record). Add `TestGetAllSalesPagination` class (5 tests: limit, offset, offset beyond total, invalid limit, invalid offset).
  - `test_product_service.py`: Fix `sample_product` fixture — `cost_price=1000.0` and `sell_price=1500.0` → `int` (float was rejected by the Phase 1 A-4 fix, leaving 3 tests in ERROR state).
  - `utils/validation/validators.py`: Restore negative-value guards in `validate_money_multiplication` that were overly stripped in Phase 0. The cap was correctly removed, but negative `amount` and negative `quantity` should still raise `ValidationException`.
- **Implemented:** All 10 new tests pass. 3 previously ERRORed tests now pass. Full suite: 181 passed, 2 skipped.

---

## Known non-issues (intentional design decisions)

- No multiuser / authentication — by design for a local desktop app.
- No event sourcing / CQRS — would be over-engineering for this scale.
- SQLite single-connection with RLock — adequate for single-process desktop use.
- No microservices — appropriate for this scope.
- No backup strategy audited — handled by `backup_service` (not in scope of this audit).
