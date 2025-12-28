# Performance and Reliability Review

## 1. Slow Query Monitoring
We have instrumented `DatabaseManager` to log any query taking longer than **50ms**.
-   **Implementation**: `time.perf_counter()` is used for high-precision measurement.
-   **Logs**: Warnings appear in the application log with the query and duration.

## 2. Database Indexing
The following indexes were added to `schema.sql` (and should be applied to existing DBs) to optimize critical paths:

| Index Name | Table(Columns) | Purpose |
| :--- | :--- | :--- |
| `idx_products_barcode` | `products(barcode)` | Accelerates "Scan" operations (Inventory/Sales) |
| `idx_products_name` | `products(name)` | Accelerates manual product search |
| `idx_sale_items_product_id` | `sale_items(product_id)` | Optimizes inventory movement history and analytics joining items to products |
| `idx_sales_date` | `sales(date)` | Optimizes date-range filtering in Analytics/Dashboard |
| `idx_sale_items_composite` | `sale_items(sale_id, product_id)` | Optimizes joining sales with specific items |
| `idx_sales_date_customer` | `sales(date, customer_id)` | Optimizes customer purchase history lookups |

## 3. Backup System Reliability
A critical flaw was identified where the backup used simple file copying (`shutil.copy2`), which could lead to corrupted backups if the database was in the middle of a write operation (especially with WAL mode).

-   **Fix**: Switched to `sqlite3`'s native [Backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup).
-   **Validation**: An automated test `tests/test_perf_backup.py` verified that backups created during active concurrent writes are consistent and valid.

## Benchmark Notes
-   **Scan Lookup**: Expected to be < 1ms with index.
-   **Backup**: Atomic snapshotting ensures data integrity without improved write locking.
