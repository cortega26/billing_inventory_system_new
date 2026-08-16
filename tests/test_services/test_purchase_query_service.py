import pytest

from services.category_service import CategoryService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.purchase_query_service import PurchaseQueryService
from services.purchase_service import PurchaseService
from utils.exceptions import ValidationException


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


def create_purchase(
    purchase_service, sample_product, supplier, date_str, quantity, cost_price
):
    purchase_service.create_purchase(
        supplier,
        date_str,
        [
            {
                "product_id": sample_product.id,
                "quantity": quantity,
                "cost_price": cost_price,
            }
        ],
    )


class TestGetPurchaseTrends:
    def test_day_interval_buckets(self, purchase_service, sample_product):
        create_purchase(
            purchase_service, sample_product, "Proveedor A", "2026-08-05", 10, 900
        )
        create_purchase(
            purchase_service, sample_product, "Proveedor A", "2026-08-10", 5, 800
        )
        create_purchase(
            purchase_service, sample_product, "Proveedor B", "2026-08-12", 3, 700
        )

        trends = PurchaseQueryService.get_purchase_trends(
            "2026-08-01", "2026-08-15", "day"
        )

        assert trends == [
            {"period": "2026-08-05", "purchase_count": 1, "total_amount": 9000},
            {"period": "2026-08-10", "purchase_count": 1, "total_amount": 4000},
            {"period": "2026-08-12", "purchase_count": 1, "total_amount": 2100},
        ]

    def test_invalid_interval_raises(self):
        with pytest.raises(ValidationException):
            PurchaseQueryService.get_purchase_trends(
                "2026-08-01", "2026-08-15", "bogus"
            )

    def test_empty_range_returns_empty_list(self):
        trends = PurchaseQueryService.get_purchase_trends(
            "2026-08-01", "2026-08-15", "day"
        )

        assert trends == []


class TestGetPurchasesBySupplier:
    def test_returns_only_matching_supplier(self, purchase_service, sample_product):
        create_purchase(
            purchase_service, sample_product, "Proveedor A", "2026-08-05", 10, 900
        )
        create_purchase(
            purchase_service, sample_product, "Proveedor A", "2026-08-10", 5, 800
        )
        create_purchase(
            purchase_service, sample_product, "Proveedor B", "2026-08-12", 3, 700
        )

        purchases = PurchaseQueryService.get_purchases_by_supplier(
            "Proveedor A", "2026-08-01", "2026-08-15"
        )

        assert len(purchases) == 2
        assert {purchase["date"] for purchase in purchases} == {
            "2026-08-05",
            "2026-08-10",
        }
        assert {purchase["total_amount"] for purchase in purchases} == {9000, 4000}
