import pytest
from services.inventory_service import InventoryService
from models.inventory import Inventory, StockStatus
from utils.exceptions import ValidationException
from models.product import Product

class TestInventoryService:
    @pytest.fixture
    def sample_product(self):
        return Product(
            id=1,
            name="Test Product",
            description="Test Description",
            category_id=1,
            cost_price=1000.0,
            sell_price=1500.0,
            barcode="12345678"
        )

    @pytest.fixture
    def inventory_service(self, db_manager):
        return InventoryService()

    def test_stock_status(self, sample_product, inventory_service, mocker):
        mock_inventory = mocker.Mock()
        mock_inventory.quantity = 10.0
        mocker.patch.object(inventory_service, 'get_inventory', return_value=mock_inventory)
        result = inventory_service.get_inventory(sample_product.id)
        assert result.quantity == 10.0

    def test_update_quantity(self, sample_product, inventory_service, mocker):
        mock_execute = mocker.patch('database.database_manager.DatabaseManager.execute_query')
        mock_execute.return_value = None
        inventory_service.update_quantity(sample_product.id, 5.0)
        mock_execute.assert_called_once()

    def test_negative_quantity_prevention(self, sample_product, inventory_service, mocker):
        # Mock existing inventory
        mock_inventory = mocker.Mock()
        mock_inventory.quantity = 10.0
        mocker.patch.object(inventory_service, 'get_inventory', return_value=mock_inventory)
        
        with pytest.raises(ValidationException):
            inventory_service.update_quantity(sample_product.id, -1.0)