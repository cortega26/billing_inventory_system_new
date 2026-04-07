from datetime import date
import inspect

import pytest

from database.database_manager import DatabaseManager
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.purchase_query_service import PurchaseQueryService
from services.purchase_service import PurchaseService
from utils.system.event_system import event_system
from utils.exceptions import NotFoundException, ValidationException


def capture_signal(signal):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    signal.connect(handler)
    return payloads, handler


@pytest.fixture
def purchase_service(db_manager):
    return PurchaseService()


@pytest.fixture
def product_service(db_manager):
    return ProductService()


@pytest.fixture
def inventory_service(db_manager):
    return InventoryService()


from services.category_service import CategoryService


@pytest.fixture
def category_service(db_manager):
    return CategoryService()


@pytest.fixture
def sample_category(category_service):
    cat_id = category_service.create_category("Test Category")
    return category_service.get_category(cat_id)


@pytest.fixture
def sample_product(product_service, sample_category):
    product_data = {
        "name": "Test Product",
        "description": "Test Description",
        "category_id": sample_category.id,
        "cost_price": 1000,
        "sell_price": 1500,
        "barcode": "12345678",
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
    def test_get_purchase_missing_returns_none(self, purchase_service):
        assert purchase_service.get_purchase(999999) is None

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

    # test_void_purchase removed as the method is deprecated/removed

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

    def test_create_purchase_rolls_back_on_invalid_product(self, purchase_service):
        invalid_data = {
            "supplier": "Broken Supplier",
            "date": date.today().isoformat(),
            "items": [{"product_id": 9999, "quantity": 10, "cost_price": 900}],
        }

        with pytest.raises(Exception):
            purchase_service.create_purchase(**invalid_data)

        assert DatabaseManager.fetch_one("SELECT id FROM purchases") is None
        assert DatabaseManager.fetch_one("SELECT id FROM purchase_items") is None

    def test_update_purchase_rolls_back_on_invalid_product(
        self, purchase_service, sample_purchase_data, inventory_service, sample_product
    ):
        purchase_id = purchase_service.create_purchase(**sample_purchase_data)

        with pytest.raises(Exception):
            purchase_service.update_purchase(
                purchase_id,
                sample_purchase_data["supplier"],
                sample_purchase_data["date"],
                [{"product_id": 9999, "quantity": 5, "cost_price": 800}],
            )

        purchase = purchase_service.get_purchase(purchase_id)
        inventory = inventory_service.get_inventory(sample_product.id)
        assert len(purchase.items) == 1
        assert purchase.items[0].quantity == 10.0
        assert inventory.quantity == 10.0

    def test_delete_purchase_missing_id_raises_not_found(self, purchase_service):
        with pytest.raises(NotFoundException):
            purchase_service.delete_purchase(999999)

    def test_update_purchase_missing_id_raises_not_found(
        self, purchase_service, sample_purchase_data
    ):
        with pytest.raises(NotFoundException):
            purchase_service.update_purchase(
                999999,
                sample_purchase_data["supplier"],
                sample_purchase_data["date"],
                sample_purchase_data["items"],
            )

    def test_create_purchase_emits_purchase_and_inventory_events_once(
        self, purchase_service, sample_purchase_data, sample_product
    ):
        purchase_payloads, purchase_handler = capture_signal(event_system.purchase_added)
        inventory_payloads, inventory_handler = capture_signal(
            event_system.inventory_changed
        )

        try:
            purchase_id = purchase_service.create_purchase(**sample_purchase_data)

            assert purchase_payloads == [purchase_id]
            assert inventory_payloads == [sample_product.id]
        finally:
            event_system.purchase_added.disconnect(purchase_handler)
            event_system.inventory_changed.disconnect(inventory_handler)

    def test_update_purchase_emits_purchase_updated_and_inventory_events_once(
        self, purchase_service, sample_purchase_data, sample_product
    ):
        purchase_id = purchase_service.create_purchase(**sample_purchase_data)
        purchase_payloads, purchase_handler = capture_signal(
            event_system.purchase_updated
        )
        inventory_payloads, inventory_handler = capture_signal(
            event_system.inventory_changed
        )

        try:
            purchase_service.update_purchase(
                purchase_id,
                sample_purchase_data["supplier"],
                sample_purchase_data["date"],
                [
                    {
                        "product_id": sample_product.id,
                        "quantity": 5,
                        "cost_price": 850,
                    }
                ],
            )

            assert purchase_payloads == [purchase_id]
            assert inventory_payloads == [sample_product.id]
        finally:
            event_system.purchase_updated.disconnect(purchase_handler)
            event_system.inventory_changed.disconnect(inventory_handler)

    def test_delete_purchase_emits_purchase_deleted_and_inventory_events_once(
        self, purchase_service, sample_purchase_data, sample_product
    ):
        purchase_id = purchase_service.create_purchase(**sample_purchase_data)
        purchase_payloads, purchase_handler = capture_signal(
            event_system.purchase_deleted
        )
        inventory_payloads, inventory_handler = capture_signal(
            event_system.inventory_changed
        )

        try:
            purchase_service.delete_purchase(purchase_id)

            assert purchase_payloads == [purchase_id]
            assert inventory_payloads == [sample_product.id]
        finally:
            event_system.purchase_deleted.disconnect(purchase_handler)
            event_system.inventory_changed.disconnect(inventory_handler)

    def test_purchase_service_declares_get_product_ids_once(self):
        source = inspect.getsource(PurchaseService)
        assert source.count("def _get_product_ids") == 1

    def test_purchase_query_service_reads_history_with_items(
        self, purchase_service, sample_purchase_data, sample_product
    ):
        purchase_id = purchase_service.create_purchase(**sample_purchase_data)

        history = PurchaseQueryService.get_purchase_history(
            sample_purchase_data["date"], sample_purchase_data["date"]
        )

        assert [purchase.id for purchase in history] == [purchase_id]
        assert history[0].items[0].product_id == sample_product.id

    def test_validate_purchase_items_rejects_excess_precision(self):
        with pytest.raises(ValidationException, match="decimal places"):
            PurchaseService._validate_purchase_items(
                [{"product_id": 1, "quantity": 1.2345, "cost_price": 900}]
            )
