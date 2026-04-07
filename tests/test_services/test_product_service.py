import pytest

from database.database_manager import DatabaseManager
from models.product import Product
from services.audit_service import AuditService
from services.category_service import CategoryService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.product_service_support import (
    build_product_update_statement,
    normalize_create_product_data,
)
from services.sale_service import SaleService
from utils.exceptions import NotFoundException, ValidationException
from utils.system.event_system import event_system


def capture_signal(signal):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    signal.connect(handler)
    return payloads, handler


class TestInventoryService:
    @pytest.fixture
    def sample_product(self):
        return Product(
            id=1,
            name="Test Product",
            description="Test Description",
            category_id=1,
            cost_price=1000,
            sell_price=1500,
            barcode="12345678",
        )

    @pytest.fixture
    def inventory_service(self, db_manager):
        return InventoryService()

    def test_stock_status(self, sample_product, inventory_service, mocker):
        mock_inventory = mocker.Mock()
        mock_inventory.quantity = 10.0
        mocker.patch.object(
            inventory_service, "get_inventory", return_value=mock_inventory
        )
        result = inventory_service.get_inventory(sample_product.id)
        assert result.quantity == 10.0

    def test_update_quantity(self, sample_product, inventory_service, mocker):
        mock_execute = mocker.patch(
            "database.database_manager.DatabaseManager.execute_query"
        )
        mock_execute.return_value = None
        inventory_service.update_quantity(sample_product.id, 5.0)
        mock_execute.assert_called_once()

    def test_negative_quantity_prevention(
        self, sample_product, inventory_service, mocker
    ):
        mock_inventory = mocker.Mock()
        mock_inventory.quantity = 10.0
        mocker.patch.object(
            inventory_service, "get_inventory", return_value=mock_inventory
        )

        with pytest.raises(Exception):
            inventory_service.update_quantity(sample_product.id, -1.0)


class TestProductServiceContracts:
    @pytest.fixture
    def product_service(self, db_manager):
        return ProductService()

    @pytest.fixture
    def category_service(self, db_manager):
        return CategoryService()

    @pytest.fixture
    def customer_service(self, db_manager):
        return CustomerService()

    @pytest.fixture
    def sale_service(self, db_manager):
        return SaleService()

    @pytest.fixture
    def inventory_service(self, db_manager):
        return InventoryService()

    def test_create_and_get_product_without_category(self, product_service):
        product_id = product_service.create_product(
            {
                "name": "Loose Item",
                "description": "No category assigned",
                "cost_price": 500,
                "sell_price": 750,
                "barcode": "12345678",
            }
        )

        product = product_service.get_product(product_id)

        assert product.category_id is None
        assert product.category_name == "Uncategorized"
        assert product.is_active is True
        assert len(
            AuditService.get_entries(
                entity_type="product",
                entity_id=product_id,
                operation="create_product",
            )
        ) == 1

    def test_get_product_missing_returns_none(self, product_service):
        assert product_service.get_product(999999) is None

    def test_create_product_validation_error_does_not_open_dialog(
        self, product_service, mocker
    ):
        show_error_dialog = mocker.patch("utils.decorators.show_error_dialog")

        with pytest.raises(ValidationException):
            product_service.create_product(
                {
                    "name": "",
                    "description": "Nombre inválido",
                    "cost_price": 500,
                    "sell_price": 900,
                    "barcode": "123456789099",
                }
            )

        show_error_dialog.assert_not_called()

    def test_normalize_create_product_data_sets_optional_defaults(self, product_service):
        normalized = normalize_create_product_data(
            {"name": "Simple product", "cost_price": 500, "sell_price": 900}
        )

        assert normalized["name"] == "Simple product"
        assert normalized["cost_price"] == 500
        assert normalized["sell_price"] == 900
        assert normalized["description"] is None
        assert normalized["category_id"] is None
        assert normalized["barcode"] is None

    def test_validate_product_data_preserves_nullable_and_barcode_fields(
        self, product_service
    ):
        validated = product_service._validate_product_data(
            {"description": "Texto", "category_id": None, "barcode": ""},
            is_create=False,
        )

        assert validated == {
            "description": "Texto",
            "category_id": None,
            "barcode": "",
        }

    def test_build_product_update_statement_uses_only_updated_fields(
        self, product_service
    ):
        query, params, updated_fields = build_product_update_statement(
            7, {"name": "Nuevo nombre", "barcode": "12345678"}
        )

        assert query == "UPDATE products SET name = :name, barcode = :barcode WHERE id = :product_id"
        assert params == {
            "name": "Nuevo nombre",
            "barcode": "12345678",
            "product_id": 7,
        }
        assert updated_fields == ["name", "barcode"]

    def test_update_product_missing_id_raises_not_found(self, product_service):
        with pytest.raises(NotFoundException):
            product_service.update_product(999999, {"name": "Inexistente"})

    def test_delete_product_archives_and_hides_from_default_listing(
        self, product_service
    ):
        product_id = product_service.create_product(
            {
                "name": "Archivable Product",
                "description": "Will be archived",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789012",
            }
        )

        product_service.delete_product(product_id)

        archived_product = product_service.get_product(product_id)
        assert archived_product.is_active is False
        assert archived_product.deleted_at is not None
        assert product_service.get_all_products() == []
        assert [product.id for product in product_service.get_all_products(active_only=False)] == [
            product_id
        ]
        assert len(
            AuditService.get_entries(
                entity_type="product",
                entity_id=product_id,
                operation="delete_product",
            )
        ) == 1

    def test_restore_product_reactivates_visibility(self, product_service):
        product_id = product_service.create_product(
            {
                "name": "Restorable Product",
                "description": "Can return to active catalog",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789013",
            }
        )
        product_service.delete_product(product_id)

        product_service.restore_product(product_id)

        restored_product = product_service.get_product(product_id)
        assert restored_product.is_active is True
        assert restored_product.deleted_at is None
        assert [product.id for product in product_service.get_all_products()] == [
            product_id
        ]
        assert len(
            AuditService.get_entries(
                entity_type="product",
                entity_id=product_id,
                operation="restore_product",
            )
        ) == 1

    def test_delete_product_with_history_archives_and_preserves_ledger(
        self,
        product_service,
        category_service,
        customer_service,
        sale_service,
        inventory_service,
    ):
        category_id = category_service.create_category("Snacks")
        product_id = product_service.create_product(
            {
                "name": "Tracked Product",
                "description": "Keeps ledger history",
                "category_id": category_id,
                "cost_price": 1000,
                "sell_price": 1500,
                "barcode": "123456789014",
            }
        )
        customer_id = customer_service.create_customer("923456780", "Ledger Customer")
        inventory_service.update_quantity(product_id, 5.0)
        sale_service.create_sale(
            customer_id,
            "2024-01-01",
            [
                {
                    "product_id": product_id,
                    "quantity": 1.0,
                    "sell_price": 1500,
                    "profit": 500,
                }
            ],
        )

        product_service.delete_product(product_id)

        archived_row = DatabaseManager.fetch_one(
            "SELECT is_active, deleted_at FROM products WHERE id = ?",
            (product_id,),
        )
        assert archived_row is not None
        assert archived_row["is_active"] == 0
        assert archived_row["deleted_at"] is not None
        assert DatabaseManager.fetch_one(
            "SELECT 1 FROM sale_items WHERE product_id = ?", (product_id,)
        )
        assert DatabaseManager.fetch_one(
            "SELECT 1 FROM inventory WHERE product_id = ?", (product_id,)
        )

    def test_search_products_excludes_archived_by_default(self, product_service):
        product_id = product_service.create_product(
            {
                "name": "Archived Search Product",
                "description": "Should not appear by default",
                "cost_price": 400,
                "sell_price": 700,
                "barcode": "123456789015",
            }
        )
        product_service.delete_product(product_id)

        assert product_service.search_products("Archived") == []
        results = product_service.search_products("Archived", active_only=False)
        assert [product.id for product in results] == [product_id]

    def test_create_product_emits_product_and_inventory_events_once(self, product_service):
        product_payloads, product_handler = capture_signal(event_system.product_added)
        inventory_payloads, inventory_handler = capture_signal(
            event_system.inventory_changed
        )

        try:
            product_id = product_service.create_product(
                {
                    "name": "Evented Product",
                    "description": "Checks signal ownership",
                    "cost_price": 500,
                    "sell_price": 900,
                    "barcode": "123456789016",
                }
            )

            assert product_payloads == [product_id]
            assert inventory_payloads == [product_id]
        finally:
            event_system.product_added.disconnect(product_handler)
            event_system.inventory_changed.disconnect(inventory_handler)

    def test_update_product_emits_product_updated_once(self, product_service):
        product_id = product_service.create_product(
            {
                "name": "Update Event Product",
                "description": "Before update",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789017",
            }
        )
        payloads, handler = capture_signal(event_system.product_updated)

        try:
            product_service.update_product(product_id, {"name": "After update"})

            assert payloads == [product_id]
        finally:
            event_system.product_updated.disconnect(handler)

    def test_delete_product_emits_product_deleted_once(self, product_service):
        product_id = product_service.create_product(
            {
                "name": "Delete Event Product",
                "description": "Before archive",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789018",
            }
        )
        payloads, handler = capture_signal(event_system.product_deleted)

        try:
            product_service.delete_product(product_id)

            assert payloads == [product_id]
        finally:
            event_system.product_deleted.disconnect(handler)

    def test_restore_product_emits_product_updated_once(self, product_service):
        product_id = product_service.create_product(
            {
                "name": "Restore Event Product",
                "description": "Before restore",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789019",
            }
        )
        product_service.delete_product(product_id)
        payloads, handler = capture_signal(event_system.product_updated)

        try:
            product_service.restore_product(product_id)

            assert payloads == [product_id]
        finally:
            event_system.product_updated.disconnect(handler)
