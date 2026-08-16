from datetime import date

import pytest

from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.sale_service import SaleService
from utils.exceptions import ValidationException
from utils.system.event_system import event_system


def capture_signal(signal):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    signal.connect(handler)
    return payloads, handler


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


from services.category_service import CategoryService  # noqa: E402


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


class TestUpdateSaleWorkflow:
    def test_two_product_swap_requires_restored_stock_validation(
        self,
        sale_service,
        sample_sale_data,
        inventory_service,
        sample_product,
        product_service,
        sample_category,
    ):
        # Product A (sample_product) sold 2; product B has only 1 in stock.
        # The update swaps to B(2): B's stock is insufficient even after A's
        # restore, so the update must fail BEFORE any mutation.
        b_id = product_service.create_product(
            {
                "name": "Product B",
                "barcode": "87654321",
                "category_id": sample_category.id,
                "cost_price": 500,
                "sell_price": 1000,
            }
        )
        inventory_service.update_quantity(b_id, 1.0)
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        swapped = [
            {"product_id": b_id, "quantity": 2, "sell_price": 1000, "profit": 1000}
        ]

        with pytest.raises(ValidationException, match="Insufficient inventory"):
            sale_service.update_sale(
                sale_id,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                swapped,
            )

        # No partial writes: sale still has product A, inventory untouched.
        sale = sale_service.get_sale(sale_id)
        assert len(sale.items) == 1
        assert sale.items[0].product_id == sample_product.id
        assert inventory_service.get_inventory(sample_product.id).quantity == 8.0
        assert inventory_service.get_inventory(b_id).quantity == 1.0

    def test_two_product_swap_succeeds_when_stock_allows_after_restore(
        self,
        sale_service,
        sample_sale_data,
        inventory_service,
        sample_product,
        product_service,
        sample_category,
    ):
        # B has exactly 2 units; available after A's restore is 2 + 0 = 2 -> OK.
        b_id = product_service.create_product(
            {
                "name": "Product B",
                "barcode": "87654321",
                "category_id": sample_category.id,
                "cost_price": 500,
                "sell_price": 1000,
            }
        )
        inventory_service.update_quantity(b_id, 2.0)
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        sale_payloads, sale_handler = capture_signal(event_system.sale_updated)
        inv_payloads, inv_handler = capture_signal(event_system.inventory_changed)
        try:
            swapped = [
                {"product_id": b_id, "quantity": 2, "sell_price": 1000, "profit": 1000}
            ]
            sale_service.update_sale(
                sale_id,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                swapped,
            )

            sale = sale_service.get_sale(sale_id)
            assert len(sale.items) == 1
            assert sale.items[0].product_id == b_id
            assert sale.items[0].quantity == 2.0
            # A fully restored, B deducted exactly once.
            assert inventory_service.get_inventory(sample_product.id).quantity == 10.0
            assert inventory_service.get_inventory(b_id).quantity == 0.0
            # Events emitted exactly once, after commit.
            assert sale_payloads == [sale_id]
            assert inv_payloads.count(b_id) == 1
        finally:
            event_system.sale_updated.disconnect(sale_handler)
            event_system.inventory_changed.disconnect(inv_handler)

    def test_update_sale_insufficient_stock_leaves_no_partial_writes(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        # Single product over-request: A sold 2 from 10; request 11 (only 10
        # available after restore) -> fail, nothing mutated.
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        oversized = [
            {
                "product_id": sample_product.id,
                "quantity": 11,
                "sell_price": sample_product.sell_price,
                "profit": 11 * (sample_product.sell_price - sample_product.cost_price),
            }
        ]
        with pytest.raises(ValidationException, match="Insufficient inventory"):
            sale_service.update_sale(
                sale_id,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                oversized,
            )

        sale = sale_service.get_sale(sale_id)
        assert len(sale.items) == 1
        assert sale.items[0].quantity == 2.0
        assert inventory_service.get_inventory(sample_product.id).quantity == 8.0
