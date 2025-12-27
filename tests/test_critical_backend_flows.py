import pytest
from datetime import datetime, timedelta
from services.inventory_service import InventoryService
from services.sale_service import SaleService
from services.purchase_service import PurchaseService
from services.product_service import ProductService
from services.category_service import CategoryService
from services.customer_service import CustomerService
from models.enums import InventoryAction, QUANTITY_PRECISION, MAX_PRICE_CLP, MAX_SALE_ITEMS
from utils.exceptions import ValidationException, DatabaseException

class TestCriticalBackendFlows:
    @pytest.fixture(autouse=True)
    def setup(self, db_manager):
        """Setup test environment with basic data."""
        self.inventory_service = InventoryService()
        self.sale_service = SaleService()
        self.purchase_service = PurchaseService()
        self.product_service = ProductService()
        self.customer_service = CustomerService()
        self.category_service = CategoryService()

        # Create basic data
        self.cat_id = self.category_service.create_category("Test Cat")
        self.prod_id = self.product_service.create_product({
            "name": "Test Product",
            "description": "Desc",
            "category_id": self.cat_id,
            "cost_price": 1000,
            "sell_price": 2000
        })
        self.cust_id = self.customer_service.create_customer("123456789", "Test Customer")

    def test_full_cycle_purchase_sale_refund(self):
        """
        Verify the complete lifecycle:
        1. Purchase stock (Inventory increases)
        2. Sell stock (Inventory decreases)
        3. Delete sale (Inventory returns)
        """
        # 1. Purchase 100 items
        items = [{"product_id": self.prod_id, "quantity": 100.0, "cost_price": 1000}]
        purchase_id = self.purchase_service.create_purchase("Supplier A", "2023-01-01", items)
        
        inventory = self.inventory_service.get_inventory(self.prod_id)
        assert inventory.quantity == 100.0

        # 2. Sell 10 items
        sale_items = [
            {"product_id": self.prod_id, "quantity": 10.0, "sell_price": 2000, "profit": 10000}
        ]
        sale_id = self.sale_service.create_sale(self.cust_id, "2023-01-02", sale_items)

        inventory = self.inventory_service.get_inventory(self.prod_id)
        assert inventory.quantity == 90.0

        # 3. Delete sale (Refund/Void)
        self.sale_service.delete_sale(sale_id)

        inventory = self.inventory_service.get_inventory(self.prod_id)
        assert inventory.quantity == 100.0

    def test_inventory_constraints_negative_stock(self):
        """Verify that selling more than available stock raises an error."""
        # Initial stock 0
        inventory = self.inventory_service.get_inventory(self.prod_id)
        current_stock = inventory.quantity if inventory else 0.0
        assert current_stock == 0.0

        # Try to sell 1 item
        sale_items = [
            {"product_id": self.prod_id, "quantity": 1.0, "sell_price": 2000, "profit": 1000}
        ]
        
        with pytest.raises(ValidationException) as excinfo:
            self.sale_service.create_sale(self.cust_id, "2023-01-01", sale_items)
        
        assert "Inventory cannot be negative" in str(excinfo.value) or "constraint failed" in str(excinfo.value)

    def test_precision_enforcement(self):
        """Verify that strictly more than QUANTITY_PRECISION decimal places raises error."""
        # 10.123 is fine
        self.inventory_service.update_quantity(self.prod_id, 10.123)
        inventory = self.inventory_service.get_inventory(self.prod_id)
        assert inventory.quantity == 10.123

        # 0.0004 has 4 decimals -> should raise ValidationException
        with pytest.raises(ValidationException) as excinfo:
             self.inventory_service.update_quantity(self.prod_id, 0.0004)
        assert "decimal places" in str(excinfo.value)

    def test_max_price_constraints(self):
        """Verify validations for max price (CLP)."""
        with pytest.raises(ValidationException) as excinfo:
            self.product_service.create_product({
                "name": "Expensive Product",
                "description": "Desc",
                "category_id": self.cat_id,
                "cost_price": MAX_PRICE_CLP + 1,
                "sell_price": 2000
            })
        assert "cannot exceed" in str(excinfo.value) or "exceeds maximum" in str(excinfo.value)

    def test_sale_edit_window(self):
        """Verify correct logic for edit window."""
        # Create a sale 1 year ago
        items = [{"product_id": self.prod_id, "quantity": 100.0, "cost_price": 1000}]
        self.purchase_service.create_purchase("Supplier A", "2022-01-01", items) # Ensure stock
        
        sale_items = [
            {"product_id": self.prod_id, "quantity": 1.0, "sell_price": 2000, "profit": 1000}
        ]
        # Manually insert an old sale since create_sale uses current time or provided string date, 
        # but the check uses creation time vs now.
        # However, `create_sale` inserts `date` column. `created_at` might be separate but `sale_service.update_sale` checks `sale.date`.
        # Code: `sale_datetime = datetime.fromisoformat(sale.date.isoformat())`
        
        # Let's try to update a sale made with a date > EDIT_WINDOW_HOURS ago
        old_date = (datetime.now() - timedelta(hours=1300)).strftime("%Y-%m-%d")
        sale_id = self.sale_service.create_sale(self.cust_id, old_date, sale_items)
        
        with pytest.raises(ValidationException) as excinfo:
            self.sale_service.update_sale(sale_id, self.cust_id, old_date, sale_items)
        
        assert "can only be edited within" in str(excinfo.value)
