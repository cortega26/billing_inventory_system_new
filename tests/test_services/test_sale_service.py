import pytest
from datetime import datetime, date
from services.sale_service import SaleService
from services.product_service import ProductService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from models.sale import Sale, SaleItem
from utils.exceptions import ValidationException, NotFoundException, BusinessLogicException
from decimal import Decimal

@pytest.fixture
def sale_service(db_manager):
    return SaleService()

@pytest.fixture
def product_service(db_manager):
    return ProductService()

@pytest.fixture
def customer_service(db_manager):
    return CustomerService()

@pytest.fixture
def inventory_service(db_manager):
    return InventoryService()

@pytest.fixture
def sample_product(product_service):
    product_data = {
        "name": "Test Product",
        "description": "Test Description",
        "category_id": 1,
        "cost_price": 1000,
        "sell_price": 1500,
        "barcode": "123456789"
    }
    product_id = product_service.create_product(product_data)
    return product_service.get_product(product_id)

@pytest.fixture
def sample_customer(customer_service):
    customer_id = customer_service.create_customer(
        identifier_9="123456789",
        name="Test Customer"
    )
    return customer_service.get_customer(customer_id)

@pytest.fixture
def sample_sale_data(sample_product, sample_customer):
    return {
        "customer_id": sample_customer.id,
        "date": date.today().isoformat(),
        "items": [
            {
                "product_id": sample_product.id,
                "quantity": 2,
                "unit_price": sample_product.sell_price
            }
        ]
    }

class TestSaleService:
    def test_create_sale(self, sale_service, sample_sale_data, inventory_service, sample_product):
        # Setup initial inventory
        inventory_service.create_inventory(sample_product.id, 10.0)

        # Create sale
        sale_id = sale_service.create_sale(**sample_sale_data)
        assert sale_id > 0

        # Verify sale was created
        sale = sale_service.get_sale(sale_id)
        assert sale.customer_id == sample_sale_data["customer_id"]
        assert len(sale.items) == 1
        assert sale.total_amount == sample_sale_data["items"][0]["quantity"] * sample_sale_data["items"][0]["unit_price"]

        # Verify inventory was updated
        inventory = inventory_service.get_inventory(sample_product.id)
        assert inventory.quantity == 8.0  # 10 - 2

    def test_create_sale_insufficient_inventory(self, sale_service, sample_sale_data, inventory_service, sample_product):
        # Setup insufficient inventory
        inventory_service.create_inventory(sample_product.id, 1.0)

        # Attempt to create sale
        with pytest.raises(BusinessLogicException):
            sale_service.create_sale(**sample_sale_data)

    def test_create_sale_invalid_quantity(self, sale_service, sample_sale_data):
        sample_sale_data["items"][0]["quantity"] = -1

        with pytest.raises(ValidationException):
            sale_service.create_sale(**sample_sale_data)

    def test_void_sale(self, sale_service, sample_sale_data, inventory_service, sample_product):
        # Setup inventory and create sale
        inventory_service.create_inventory(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        # Void the sale
        sale_service.void_sale(sale_id)

        # Verify sale is marked as voided
        sale = sale_service.get_sale(sale_id)
        assert sale.is_voided

        # Verify inventory was restored
        inventory = inventory_service.get_inventory(sample_product.id)
        assert inventory.quantity == 10.0

    def test_get_sales_by_date_range(self, sale_service, sample_sale_data):
        # Create multiple sales
        sale_service.create_sale(**sample_sale_data)
        
        # Get sales for today
        today = date.today().isoformat()
        sales = sale_service.get_sales_by_date_range(today, today)
        assert len(sales) == 1

    def test_get_customer_sales(self, sale_service, sample_sale_data, sample_customer):
        sale_service.create_sale(**sample_sale_data)
        
        # Get sales for customer
        sales = sale_service.get_customer_sales(sample_customer.id)
        assert len(sales) == 1
        assert sales[0].customer_id == sample_customer.id

    def test_calculate_sale_totals(self, sale_service, sample_sale_data):
        sale_id = sale_service.create_sale(**sample_sale_data)
        sale = sale_service.get_sale(sale_id)

        # Verify totals
        expected_total = sample_sale_data["items"][0]["quantity"] * sample_sale_data["items"][0]["unit_price"]
        assert sale.total_amount == expected_total
        assert sale.total_profit > 0  # Profit should be positive since sell_price > cost_price

    def test_update_sale_receipt(self, sale_service, sample_sale_data):
        sale_id = sale_service.create_sale(**sample_sale_data)
        
        # Update receipt number
        receipt_id = "R123456"
        sale_service.update_sale_receipt(sale_id, receipt_id)
        
        # Verify update
        sale = sale_service.get_sale(sale_id)
        assert sale.receipt_id == receipt_id

    def test_get_sale_statistics(self, sale_service, sample_sale_data):
        sale_service.create_sale(**sample_sale_data)
        
        # Get statistics for today
        today = date.today().isoformat()
        stats = sale_service.get_sale_statistics(today, today)
        
        assert stats["total_sales"] == 1
        assert stats["total_amount"] > 0
        assert stats["total_profit"] > 0 