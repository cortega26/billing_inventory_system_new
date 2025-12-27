from datetime import date

import pytest

from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.purchase_service import PurchaseService
from utils.exceptions import (
    ValidationException,
)


@pytest.fixture
def purchase_service(db_manager):
    return PurchaseService()


@pytest.fixture
def product_service(db_manager):
    return ProductService()


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
        "barcode": "12345678",  # 8 digits barcode
    }
    product_id = product_service.create_product(product_data)
    return product_service.get_product(product_id)


@pytest.fixture
def sample_purchase_data(sample_product):
    return {
        "supplier": "Test Supplier",
        "date": date.today().isoformat(),
        "items": [
            {
                "product_id": sample_product.id,
                "quantity": 10,
                "cost_price": 900,  # Purchase price (was price)
            }
        ],
    }


class TestPurchaseService:
    def test_create_purchase(
        self, purchase_service, sample_purchase_data, inventory_service, sample_product
    ):
        # Create purchase
        purchase_id = purchase_service.create_purchase(**sample_purchase_data)
        assert purchase_id > 0

        # Verify purchase was created
        purchase = purchase_service.get_purchase(purchase_id)
        assert purchase.supplier == sample_purchase_data["supplier"]
        assert len(purchase.items) == 1

        # Verify inventory was updated
        inventory = inventory_service.get_inventory(sample_product.id)
        assert inventory.quantity == 10.0

    def test_invalid_purchase(self, purchase_service):
        """Test creating purchase with invalid data."""
        invalid_data = {
            "supplier": "",  # Empty supplier
            "date": date.today().isoformat(),
            "items": [],  # No items
        }

        with pytest.raises(ValidationException):
            purchase_service.create_purchase(**invalid_data)

    def test_get_purchase_history(self, purchase_service, sample_purchase_data):
        # Create purchase
        purchase_service.create_purchase(**sample_purchase_data)

        # Get history
        today = date.today().isoformat()
        history = purchase_service.get_purchase_history(today, today)

        assert len(history) == 1
        assert history[0].supplier == sample_purchase_data["supplier"]

    def test_void_purchase(
        self, purchase_service, sample_purchase_data, inventory_service, sample_product
    ):
        # Create purchase
        purchase_id = purchase_service.create_purchase(**sample_purchase_data)

        # Void purchase
        purchase_service.void_purchase(purchase_id)

        # Verify inventory was updated
        inventory = inventory_service.get_inventory(sample_product.id)
        assert inventory.quantity == 0.0

    def test_get_supplier_purchases(self, purchase_service, sample_purchase_data):
        # Create purchase
        purchase_service.create_purchase(**sample_purchase_data)

        # Get supplier purchases
        supplier = sample_purchase_data["supplier"]
        purchases = purchase_service.get_supplier_purchases(supplier)

        assert len(purchases) == 1
        assert purchases[0].supplier == supplier

    def test_get_top_suppliers(self, purchase_service, sample_purchase_data):
        # Create multiple purchases from same supplier
        purchase_service.create_purchase(**sample_purchase_data)
        purchase_service.create_purchase(**sample_purchase_data)

        # Get top suppliers
        today = date.today().isoformat()
        top_suppliers = purchase_service.get_top_suppliers(today, today)

        assert len(top_suppliers) > 0
        assert top_suppliers[0]["supplier"] == sample_purchase_data["supplier"]
        assert top_suppliers[0]["purchase_count"] == 2

    def test_get_purchase_statistics(self, purchase_service, sample_purchase_data):
        purchase_service.create_purchase(**sample_purchase_data)

        # Get statistics for today
        today = date.today().isoformat()
        stats = purchase_service.get_purchase_statistics(today, today)

        assert stats["total_purchases"] == 1
        assert stats["total_amount"] > 0
        assert len(stats["suppliers"]) == 1
