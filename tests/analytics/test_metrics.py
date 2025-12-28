import sqlite3
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from services.analytics.engine import AnalyticsEngine
from services.analytics.metrics import (
    SalesDailyMetric,
    TopProductsMetric,
    LowStockMetric,
    InventoryAgingMetric,
    DepartmentSalesMetric
)

# --- Fixtures ---

@pytest.fixture
def analytics_db_path(tmp_path):
    """Creates a temporary database with a seeded schema and data."""
    db_file = tmp_path / "test_analytics.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Schema
    cursor.executescript("""
        CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, 
            name TEXT, 
            category_id INTEGER,
            cost_price INTEGER,
            sell_price INTEGER
        );
        CREATE TABLE inventory (
            product_id INTEGER PRIMARY KEY, 
            quantity DECIMAL(10,3)
        );
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY, 
            date TEXT, 
            total_amount INTEGER
        );
        CREATE TABLE sale_items (
            id INTEGER PRIMARY KEY, 
            sale_id INTEGER, 
            product_id INTEGER, 
            quantity DECIMAL(10,3), 
            price INTEGER
        );
    """)

    # Seed Data
    # Categories
    cursor.execute("INSERT INTO categories (id, name) VALUES (1, 'Electronics')")
    cursor.execute("INSERT INTO categories (id, name) VALUES (2, 'Clothing')")

    # Products
    # 1: Laptop (Elec)
    # 2: T-Shirt (Cloth)
    # 3: Old Phone (Elec) - Dead stock
    cursor.execute("INSERT INTO products VALUES (1, 'Laptop', 1, 500, 1000)")
    cursor.execute("INSERT INTO products VALUES (2, 'T-Shirt', 2, 10, 20)")
    cursor.execute("INSERT INTO products VALUES (3, 'Old Phone', 1, 50, 100)")

    # Inventory
    cursor.execute("INSERT INTO inventory VALUES (1, 10)")  # Laptop: 10
    cursor.execute("INSERT INTO inventory VALUES (2, 5)")   # T-Shirt: 5 (Low stock < 10)
    cursor.execute("INSERT INTO inventory VALUES (3, 50)")  # Old Phone: 50 (Dead stock)

    # Sales
    # Sale 1: Yesterday - 2 Laptops
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO sales VALUES (1, ?, 2000)", (yesterday,))
    cursor.execute("INSERT INTO sale_items VALUES (1, 1, 1, 2, 1000)")

    # Sale 2: Today - 1 Laptop, 5 T-Shirts
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO sales VALUES (2, ?, 1100)", (today,))
    cursor.execute("INSERT INTO sale_items VALUES (2, 2, 1, 1, 1000)")
    cursor.execute("INSERT INTO sale_items VALUES (3, 2, 2, 5, 20)")

    conn.commit()
    conn.close()
    return db_file

@pytest.fixture
def engine(analytics_db_path):
    return AnalyticsEngine(db_path=analytics_db_path)

# --- Tests ---

def test_sales_daily(engine):
    start = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    metric = SalesDailyMetric()
    result = engine.execute_metric(metric, start_date=start, end_date=end)
    
    # We expect 2 entries (yesterday and today)
    assert len(result.data) == 2
    
    # Validate structure
    assert "date" in result.data[0]
    assert "total_sales" in result.data[0]
    
    # Validate sums
    # Yesterday: 2000
    # Today: 1100
    total = sum(d["total_sales"] for d in result.data)
    assert total == 3100


def test_top_products(engine):
    start = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    metric = TopProductsMetric()
    result = engine.execute_metric(metric, start_date=start, end_date=end, limit=5)
    
    # Top product should be T-Shirt (quantity 5) or Laptop (quantity 2+1=3)
    # Wait, T-Shirt sold 5 units. Laptop sold 2+1=3.
    # So T-Shirt is #1.
    
    assert len(result.data) == 2
    top_product = result.data[0]
    assert top_product["name"] == "T-Shirt"
    assert top_product["total_quantity"] == 5


def test_low_stock(engine):
    metric = LowStockMetric()
    result = engine.execute_metric(metric, threshold=10)
    
    # Only T-Shirt (5) should be returned (less than 10)
    # Laptop is 10 (not less than 10)
    # Old Phone is 50
    
    assert len(result.data) == 1
    assert result.data[0]["name"] == "T-Shirt"
    assert result.data[0]["quantity"] == 5


def test_inventory_aging(engine):
    # Old Phone has stock (50) but NO sales.
    # Other products have sales recently.
    
    metric = InventoryAgingMetric()
    result = engine.execute_metric(metric, days=30)
    
    # Should find 'Old Phone'
    found_names = [d["name"] for d in result.data]
    assert "Old Phone" in found_names
    assert "Laptop" not in found_names  # Sold today/yesterday
    assert "T-Shirt" not in found_names # Sold today


def test_department_sales(engine):
    start = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    metric = DepartmentSalesMetric()
    result = engine.execute_metric(metric, start_date=start, end_date=end)
    
    # Categories: Electronics (1), Clothing (2)
    # Electronics Sales: 2*1000 + 1*1000 = 3000
    # Clothing Sales: 5*20 = 100
    
    data_map = {d["category"]: d["total_sales"] for d in result.data}
    
    assert data_map["Electronics"] == 3000
    assert data_map["Clothing"] == 100
