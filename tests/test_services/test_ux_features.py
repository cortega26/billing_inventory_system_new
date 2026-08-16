from datetime import datetime

import pytest

from services.category_service import CategoryService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.sale_service import SaleService


class TestUXFeatures:
    @pytest.fixture(autouse=True)
    def setup(self, db_manager):
        self.inventory_service = InventoryService()
        self.sale_service = SaleService()
        self.product_service = ProductService()
        self.customer_service = CustomerService()
        self.category_service = CategoryService()
        self.cat_id = self.category_service.create_category("Test Category")

    def test_low_stock_threshold(self):
        # Create products
        p1_id = self.product_service.create_product(
            {
                "name": "Low Item",
                "barcode": "11111111",
                "category_id": self.cat_id,
                "sell_price": 100,
                "cost_price": 50,
                "stock_quantity": 0,
            }
        )
        p2_id = self.product_service.create_product(
            {
                "name": "High Item",
                "barcode": "22222222",
                "category_id": self.cat_id,
                "sell_price": 100,
                "cost_price": 50,
                "stock_quantity": 0,
            }
        )

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
        p_id = self.product_service.create_product(
            {
                "name": "Test Product",
                "barcode": "33333333",
                "sell_price": 1000,
                "cost_price": 500,
            }
        )
        self.inventory_service.set_quantity(p_id, 100.0)

        today = datetime.now().strftime("%Y-%m-%d")

        items = [
            {
                "product_id": p_id,
                "quantity": 2.0,
                "sell_price": 1000,
                "profit": 1000,  # 2 * (1000-500)
            }
        ]

        self.sale_service.create_sale(cust_id, today, items)

        # Get total sales for today
        todays_sales = self.sale_service.get_total_sales(today, today)
        assert todays_sales == 2000
