
import sys
import os
sys.path.append(os.getcwd())

import pytest
from datetime import datetime
from services.inventory_service import InventoryService
from services.sale_service import SaleService
from services.product_service import ProductService
from services.customer_service import CustomerService
from database.database_manager import DatabaseManager
from models.enums import InventoryAction
from services.category_service import CategoryService

def test_manual():
    print("Initializing DB...")
    DatabaseManager.initialize(":memory:")
    # Load schema
    with open("schema.sql", "r") as f:
         with DatabaseManager.get_db_connection() as conn:
             conn.executescript(f.read())

    print("Setup Services...")
    inventory_service = InventoryService()
    sale_service = SaleService()
    product_service = ProductService()
    customer_service = CustomerService()

    from services.category_service import CategoryService
    category_service = CategoryService()
    cat_id = category_service.create_category("Test Category")

    print("Testing Low Stock...")
    # Create products
    p1_id = product_service.create_product({
        "name": "Low Item", "barcode": "11111111", "category_id": cat_id, "sell_price": 100, "cost_price": 50, "stock_quantity": 0, "description": "Test Desc"
    })
    p2_id = product_service.create_product({
        "name": "High Item", "barcode": "22222222", "category_id": cat_id, "sell_price": 100, "cost_price": 50, "stock_quantity": 0, "description": "Test Desc"
    })

    # Set inventory
    inventory_service.set_quantity(p1_id, 3.0)
    inventory_service.set_quantity(p2_id, 15.0)

    # Test default threshold (10)
    low_stock = inventory_service.get_low_stock_products()
    assert len(low_stock) == 1
    assert low_stock[0]["id"] == p1_id
    print("  Default threshold OK")

    # Test custom threshold (20)
    low_stock_20 = inventory_service.get_low_stock_products(threshold=20)
    assert len(low_stock_20) == 2
    print("  Threshold 20 OK")

    # Test custom threshold (2)
    low_stock_2 = inventory_service.get_low_stock_products(threshold=2)
    assert len(low_stock_2) == 0
    print("  Threshold 2 OK")

    print("Testing Today's Sales...")
    # Create sale for today
    cust_id = customer_service.create_customer("999999999", "Test Customer")
    p_id = product_service.create_product({
        "name": "Test Product", "barcode": "33333333", "sell_price": 1000, "cost_price": 500, "stock_quantity": 100, "description": "Test Desc", "category_id": cat_id
    })
    
    today = datetime.now().strftime("%Y-%m-%d")
    inventory_service.set_quantity(p_id, 100.0)
    
    items = [{
        "product_id": p_id,
        "quantity": 2.0,
        "sell_price": 1000,
        "profit": 1000 
    }]
    
    sale_service.create_sale(cust_id, today, items)

    # Get total sales for today
    todays_sales = sale_service.get_total_sales(today, today)
    assert todays_sales == 2000
    print("  Today's Sales OK")

if __name__ == "__main__":
    try:
        test_manual()
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()


class TestUXFeatures:
    @pytest.fixture(autouse=True)
    def setup(self):
        DatabaseManager.initialize()
        # Clean up
        DatabaseManager.execute_query("DELETE FROM sale_items")
        DatabaseManager.execute_query("DELETE FROM sales")
        DatabaseManager.execute_query("DELETE FROM inventory")
        DatabaseManager.execute_query("DELETE FROM products")
        DatabaseManager.execute_query("DELETE FROM customers")
        
        self.inventory_service = InventoryService()
        self.sale_service = SaleService()
        self.product_service = ProductService()
        self.product_service = ProductService()
        self.customer_service = CustomerService()
        self.category_service = CategoryService()
        self.cat_id = self.category_service.create_category("Test Category")

    def test_low_stock_threshold(self):
        # Create products
        p1_id = self.product_service.create_product({
            "name": "Low Item", "barcode": "11111111", "category_id": self.cat_id, "sell_price": 100, "cost_price": 50, "stock_quantity": 0
        })
        p2_id = self.product_service.create_product({
            "name": "High Item", "barcode": "22222222", "category_id": self.cat_id, "sell_price": 100, "cost_price": 50, "stock_quantity": 0
        })

        # Set inventory
        self.inventory_service.set_quantity(p1_id, 3.0)
        self.inventory_service.set_quantity(p2_id, 15.0)

        # Test default threshold (10)
        low_stock = self.inventory_service.get_low_stock_products()
        assert len(low_stock) == 1
        assert low_stock[0]["id"] == p1_id

        # Test custom threshold (20)
        low_stock_20 = self.inventory_service.get_low_stock_products(threshold=20)
        assert len(low_stock_20) == 2

        # Test custom threshold (2)
        low_stock_2 = self.inventory_service.get_low_stock_products(threshold=2)
        assert len(low_stock_2) == 0

    def test_todays_sales(self):
        # Create sale for today
        cust_id = self.customer_service.create_customer("999999999", "Test Customer")
        p_id = self.product_service.create_product({
            "name": "Test Product", "barcode": "33333333", "sell_price": 1000, "cost_price": 500
        })
        self.inventory_service.set_quantity(p_id, 100.0)
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        items = [{
            "product_id": p_id,
            "quantity": 2.0,
            "sell_price": 1000,
            "profit": 1000 # 2 * (1000-500)
        }]
        
        self.sale_service.create_sale(cust_id, today, items)

        # Get total sales for today
        todays_sales = self.sale_service.get_total_sales(today, today)
        assert todays_sales == 2000

