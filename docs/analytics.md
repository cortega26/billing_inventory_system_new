# Advanced Analytics V1

This module (`services/analytics`) provides a dedicated, read-only interface for querying business performance metrics.

## Architecture

- **Read-Only Access**: Uses a separate SQLite connection with `mode=ro` to ensure analytics queries never modify data.
- **Metric Contracts**: Each metric is defined as a class inheriting from `Metric`, specifying its name, parameters, query, and output schema.
- **Engine**: The `AnalyticsEngine` executes these metrics safely.

## Available Metrics

### 1. Daily Sales (`sales_daily`)

Aggregates total sales and transaction counts per day.

**Parameters:**
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)

**Example Output:**
```json
[
  {
    "date": "2023-10-25",
    "total_sales": 150000,
    "sale_count": 12
  },
  {
    "date": "2023-10-26",
    "total_sales": 200500,
    "sale_count": 18
  }
]
```

### 2. Top Products (`top_products`)

Identifies best-selling products by quantity.

**Parameters:**
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)
- `limit` (int, default=10)

**Example Output:**
```json
[
  {
    "product_id": 101,
    "name": "Wireless Mouse",
    "total_quantity": 45,
    "total_revenue": 450000
  },
  {
    "product_id": 55,
    "name": "USB Cable",
    "total_quantity": 30,
    "total_revenue": 90000
  }
]
```

### 3. Low Stock (`low_stock`)

Lists products with inventory below a specific threshold.

**Parameters:**
- `threshold` (float, default=10)

**Example Output:**
```json
[
  {
    "product_id": 101,
    "name": "Wireless Mouse",
    "quantity": 2
  }
]
```

### 4. Inventory Aging (`inventory_aging`)

Identifies "dead stock" or slow movers: products with positive stock that haven't been sold for `N` days.

**Parameters:**
- `days` (int, default=30)

**Example Output:**
```json
[
  {
    "product_id": 202,
    "name": "Old VGA Cable",
    "stock_quantity": 15,
    "last_sold_date": "2023-01-15"
  },
  {
    "product_id": 303,
    "name": "Floppy Disk",
    "stock_quantity": 50,
    "last_sold_date": null 
  }
]
```
*(Note: `last_sold_date` is `null` if the product has never been sold)*

### 5. Sales by Department (`department_sales`)

Groups sales performance by product category.

**Parameters:**
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)

**Example Output:**
```json
[
  {
    "category": "Electronics",
    "total_sales": 1500000,
    "units_sold": 150
  },
  {
    "category": "Accessories",
    "total_sales": 300000,
    "units_sold": 500
  }
]
```

## Usage

```python
from services.analytics import AnalyticsEngine, SalesDailyMetric

engine = AnalyticsEngine()
metric = SalesDailyMetric()

result = engine.execute_metric(
    metric, 
    start_date="2023-01-01", 
    end_date="2023-01-31"
)

print(result.data)
```
