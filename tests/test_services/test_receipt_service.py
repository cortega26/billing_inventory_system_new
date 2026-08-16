from datetime import date

import pytest

from services.category_service import CategoryService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.sale_service import SaleService
from utils.exceptions import ValidationException


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
def category_service(db_manager):
    return CategoryService()


@pytest.fixture
def inventory_service(db_manager):
    return InventoryService()


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
def sample_customer(customer_service):
    customer_id = customer_service.create_customer(
        identifier_9="923456789", name="Test Customer"
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
                "sell_price": sample_product.sell_price,
                "profit": 2 * (sample_product.sell_price - sample_product.cost_price),
            }
        ],
    }


@pytest.fixture
def seeded_sale(sale_service, sample_sale_data, inventory_service, sample_product):
    inventory_service.update_quantity(sample_product.id, 10.0)
    return sale_service.create_sale(**sample_sale_data)


class TestSaveReceiptAsPdf:
    def test_generates_pdf_file(self, sale_service, seeded_sale, tmp_path):
        pdf_path = tmp_path / "receipt.pdf"
        sale_service.save_receipt_as_pdf(seeded_sale, str(pdf_path))

        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0
        with pdf_path.open("rb") as f:
            assert f.read(4) == b"%PDF"


class TestSendReceiptViaWhatsApp:
    def test_placeholder_returns_none(self, sale_service, seeded_sale):
        result = sale_service.send_receipt_via_whatsapp(seeded_sale, "912345678")

        assert result is None

    def test_phone_too_long_raises(self, sale_service):
        with pytest.raises(ValidationException):
            sale_service.send_receipt_via_whatsapp(1, "9" * 25)
