import pytest

from models.category import Category
from models.product import Product
from utils.exceptions import ValidationException


@pytest.fixture
def sample_category():
    return Category(id=1, name="Test Category")


@pytest.fixture
def sample_product(sample_category):
    return Product(
        id=1,
        name="Test Product",
        description="Test Description",
        category_id=sample_category.id,
        cost_price=1000.0,
        sell_price=1500.0,
        barcode="12345678",
    )


class TestProduct:
    def test_product_creation(self, sample_product):
        assert sample_product.id == 1
        assert sample_product.name == "Test Product"
        assert float(sample_product.cost_price) == 1000.0
        assert float(sample_product.sell_price) == 1500.0

    def test_invalid_price(self):
        with pytest.raises(ValidationException):
            Product(
                id=1,
                name="Test Product",
                description="Test",
                category_id=1,
                cost_price=-1000.0,
                sell_price=1500.0,
                barcode="12345678",
            )

    def test_profit_margin_calculation(self, sample_product):
        # Expected margin: (1500 - 1000) / 1500 * 100 = 33.33%
        assert sample_product.calculate_profit_margin() == 33.33

    def test_profit_calculation(self, sample_product):
        # Expected profit: 1500 - 1000 = 500
        assert sample_product.calculate_profit() == 500

    def test_to_dict(self, sample_product):
        product_dict = sample_product.to_dict()
        assert product_dict["id"] == 1
        assert product_dict["name"] == "Test Product"
        assert product_dict["cost_price"] == 1000.0
        assert product_dict["sell_price"] == 1500.0

    def test_barcode_validation(self):
        """Test barcode validation."""
        # Valid barcode (8 digits)
        product = Product(
            id=1,
            name="Test Product",
            category_id=1,
            barcode="12345678",
            cost_price=100,
            sell_price=200,
            description="Test",
        )
        product.validate()

        # Invalid barcode (wrong length)
        with pytest.raises(ValidationException):
            Product(
                id=1,
                name="Test Product",
                category_id=1,
                barcode="1234567",  # 7 digits - too short
                cost_price=100,
                sell_price=200,
                description="Test",
            ).validate()
