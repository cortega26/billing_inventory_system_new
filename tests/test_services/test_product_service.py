import pytest

from database.database_manager import DatabaseManager
from models.product import Product
from services.category_service import CategoryService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.sale_service import SaleService
from utils.exceptions import ValidationException


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
        # Mock existing inventory
        mock_inventory = mocker.Mock()
        mock_inventory.quantity = 10.0
        mocker.patch.object(
            inventory_service, "get_inventory", return_value=mock_inventory
        )

        with pytest.raises(ValidationException):
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

    def test_delete_product_with_history_is_rejected(
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
                "barcode": "123456789012",
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

        with pytest.raises(ValidationException):
            product_service.delete_product(product_id)

        assert DatabaseManager.fetch_one(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        )
        assert DatabaseManager.fetch_one(
            "SELECT 1 FROM sale_items WHERE product_id = ?", (product_id,)
        )
