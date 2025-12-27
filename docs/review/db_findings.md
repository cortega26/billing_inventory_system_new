# Database Schema & Data Integrity Audit

## 1. Executive Summary
The current SQLite schema is functional but lacks enforcement of key business invariants at the database level. Reliance on application-layer validation (`services/*.py`) creates a risk of data corruption if direct DB access occurs or bugs are introduced.

We recommend **retaining the current "Virtual Ledger" strategy** (computing stock from movements) rather than a materializing ledger table, as it ensures zero desync risk between sales/purchases and stock levels.

## 2. Findings & Recommendations

### A. Missing Constraints (High Priority)
| Table | Column | Issue | Recommendation |
| :--- | :--- | :--- | :--- |
| `inventory` | `quantity` | Can be negative | Add `CHECK (quantity >= 0)` (unless overdraft allowed) |
| `products` | `cost_price` | Can be negative | Add `CHECK (cost_price >= 0)` |
| `products` | `sell_price` | Can be negative | Add `CHECK (sell_price >= 0)` |
| `sale_items` | `profit` | No validation | Add `CHECK (profit = (price - product.cost_price) * quantity)` (Calculated column in SQLite generated/check?) - *Complex, maybe skip for now, settle for NOT NULL* |

### B. Foreign Keys
- `ON DELETE` actions are unspecified.
- **Risk**: Deleting a `Product` leaves `SaleItem` rows orphaned.
- **Fix**: Add `ON DELETE RESTRICT` to `sale_items.product_id` and `purchase_items.product_id` to prevent deletion of products with history.

### C. Indexes
- Current indexes in `migrations.py` are good.
- **Missing**: `inventory(product_id)` (It's a PK? No, `id` is PK. `product_id` is UNIQUE). `product_id` is unique so it has an index. **OK.**

## 3. Stock Management Strategy: "Virtual Ledger"

### Current Approach
Stock at time $T$ is calculated by:
$$ Inventory_T = \sum (Purchases) - \sum (Sales) + \sum (Adjustments) $$

### Justification for Retention
1.  **Single Source of Truth**: Data exists only in `sales`, `purchases`, and `adjustments`. A separate `ledger` table would duplicate this data.
2.  **Consistency**: It is mathematically impossible for the "ledger" to drift from the "sales history" because the history *is* the ledger.
3.  **Traceability**: Every stock change is linked to a business event (Sale #123, Purchase #456).

### Verification
We will enforce this with a **View** (optional) or Service method that performs this aggregation, which already exists in `InventoryService.get_inventory_movements`.

## 4. Migration Plan
Since SQLite does not support `ALTER TABLE ADD CONSTRAINT` easily:
1.  **New Installs**: Update `schema.sql` immediately.
2.  **Existing Installs**:
    - We cannot easily rebuild tables in-place without strict locking and data copying script.
    - **Action**: We will apply strict `CHECK` constraints to `schema.sql` for future reference. For existing DBs, we rely on the Service Layer validation (which is already robust) and adding a `verify_integrity()` tool.

## 5. Proposed Schema Updates

```sql
CREATE TABLE products (
    -- ...
    cost_price INTEGER NOT NULL DEFAULT 0 CHECK (cost_price >= 0),
    sell_price INTEGER NOT NULL DEFAULT 0 CHECK (sell_price >= 0)
    -- ...
);

CREATE TABLE inventory (
    -- ...
    quantity DECIMAL(10,3) NOT NULL DEFAULT 0.000 CHECK (quantity >= 0)
    -- ...
);
```
