from datetime import date

import pytest

from database.database_manager import DatabaseManager
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.sale_service import SaleService
from utils.exceptions import NotFoundException, ValidationException
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


class TestSaleService:
    def test_get_sale_missing_returns_none(self, sale_service):
        assert sale_service.get_sale(999999) is None

    def test_create_sale(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        # Setup initial inventory
        inventory_service.update_quantity(sample_product.id, 10.0)

        # Create sale
        sale_id = sale_service.create_sale(**sample_sale_data)
        assert sale_id > 0

        # Verify sale was created
        sale = sale_service.get_sale(sale_id)
        assert sale.customer_id == sample_sale_data["customer_id"]
        assert len(sale.items) == 1
        assert (
            sale.total_amount
            == sample_sale_data["items"][0]["quantity"]
            * sample_sale_data["items"][0]["sell_price"]
        )

        # Verify inventory was updated
        inventory = inventory_service.get_inventory(sample_product.id)
        assert inventory.quantity == 8.0  # 10 - 2

    def test_create_sale_insufficient_inventory(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        # Setup insufficient inventory
        inventory_service.update_quantity(sample_product.id, 1.0)

        # Attempt to create sale
        with pytest.raises(ValidationException):
            sale_service.create_sale(**sample_sale_data)

        assert DatabaseManager.fetch_one("SELECT id FROM sales") is None
        assert DatabaseManager.fetch_one("SELECT id FROM sale_items") is None

    def test_create_sale_invalid_quantity(self, sale_service, sample_sale_data):
        sample_sale_data["items"][0]["quantity"] = -1

        with pytest.raises(ValidationException):
            sale_service.create_sale(**sample_sale_data)

    def test_get_sales_by_date_range(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        # Setup inventory
        inventory_service.update_quantity(sample_product.id, 10.0)
        # Create multiple sales
        sale_service.create_sale(**sample_sale_data)

        # Get sales for today
        today = date.today().isoformat()
        sales = sale_service.get_sales_by_date_range(today, today)
        assert len(sales) == 1

    def test_calculate_sale_totals(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        sale = sale_service.get_sale(sale_id)

        # Verify totals
        expected_total = (
            sample_sale_data["items"][0]["quantity"]
            * sample_sale_data["items"][0]["sell_price"]
        )
        assert sale.total_amount == expected_total
        assert (
            sale.total_profit > 0
        )  # Profit should be positive since sell_price > cost_price

    def test_get_sale_statistics(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_service.create_sale(**sample_sale_data)

        # Get statistics for today
        today = date.today().isoformat()
        stats = sale_service.get_sale_statistics(today, today)

        assert stats["total_sales"] == 1
        assert stats["total_amount"] > 0
        assert stats["total_profit"] > 0

    def test_get_total_sales_excludes_cancelled_sales(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        today = date.today().isoformat()
        assert sale_service.get_total_sales(today, today) > 0
        sale_service.cancel_sale(sale_id)
        assert sale_service.get_total_sales(today, today) == 0

    def test_get_total_profits_excludes_cancelled_sales(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        today = date.today().isoformat()
        assert sale_service.get_total_profits(today, today) > 0
        sale_service.cancel_sale(sale_id)
        assert sale_service.get_total_profits(today, today) == 0

    def test_get_total_units_sold_sums_confirmed_sales(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sample_sale_data["items"][0]["quantity"] = 2.5
        sale_service.create_sale(**sample_sale_data)
        today = date.today().isoformat()
        assert sale_service.get_total_units_sold(today, today) == 2.5

    def test_get_total_units_sold_excludes_cancelled_sales(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        today = date.today().isoformat()
        assert sale_service.get_total_units_sold(today, today) == 2.0
        sale_service.cancel_sale(sale_id)
        assert sale_service.get_total_units_sold(today, today) == 0

    def test_get_sale_statistics_excludes_cancelled_sales(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        today = date.today().isoformat()
        sale_service.cancel_sale(sale_id)
        stats = sale_service.get_sale_statistics(today, today)
        assert stats["total_sales"] == 0
        assert stats["total_amount"] == 0
        assert stats["total_profit"] == 0

    def test_get_sale_after_customer_deleted(
        self,
        sale_service,
        sample_sale_data,
        inventory_service,
        sample_product,
        customer_service,
        sample_customer,
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        customer_service.delete_customer(sample_customer.id)

        sale = sale_service.get_sale(sale_id)
        assert sale.customer_id == sample_customer.id
        assert len(sale.items) == 1

    def test_update_historical_sale_is_allowed(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        historical_date = "2020-01-01"
        sale_id = sale_service.create_sale(
            sample_sale_data["customer_id"],
            historical_date,
            sample_sale_data["items"],
        )

        updated_items = [
            {
                "product_id": sample_product.id,
                "quantity": 1,
                "sell_price": sample_product.sell_price,
                "profit": sample_product.sell_price - sample_product.cost_price,
            }
        ]

        sale_service.update_sale(
            sale_id,
            sample_sale_data["customer_id"],
            historical_date,
            updated_items,
        )

        sale = sale_service.get_sale(sale_id)
        inventory = inventory_service.get_inventory(sample_product.id)
        assert len(sale.items) == 1
        assert sale.items[0].quantity == 1.0
        assert inventory.quantity == 9.0

    def test_update_sale_stores_quantity_as_number(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(
            sample_sale_data["customer_id"],
            sample_sale_data["date"],
            sample_sale_data["items"],
        )

        updated_items = [
            {
                "product_id": sample_product.id,
                "quantity": 1,
                "sell_price": sample_product.sell_price,
                "profit": sample_product.sell_price - sample_product.cost_price,
            }
        ]
        sale_service.update_sale(
            sale_id,
            sample_sale_data["customer_id"],
            sample_sale_data["date"],
            updated_items,
        )

        row = DatabaseManager.fetch_one(
            "SELECT typeof(quantity) as type FROM sale_items WHERE sale_id = ?",
            (sale_id,),
        )
        assert row["type"] == "real"

    def test_update_sale_rolls_back_on_insufficient_inventory(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        with pytest.raises(ValidationException):
            sale_service.update_sale(
                sale_id,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                [
                    {
                        "product_id": sample_product.id,
                        "quantity": 11,
                        "sell_price": sample_product.sell_price,
                        "profit": 11
                        * (sample_product.sell_price - sample_product.cost_price),
                    }
                ],
            )

        sale = sale_service.get_sale(sale_id)
        inventory = inventory_service.get_inventory(sample_product.id)
        assert sale.items[0].quantity == 2.0
        assert inventory.quantity == 8.0

    def test_update_sale_insufficient_inventory_fails_before_mutation(
        self,
        sale_service,
        sample_sale_data,
        inventory_service,
        sample_product,
        monkeypatch,
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        def _should_not_update_sale(*args, **kwargs):
            raise AssertionError("_update_sale should not run on pre-check failure")

        monkeypatch.setattr(
            SaleService,
            "_update_sale",
            staticmethod(_should_not_update_sale),
        )

        with pytest.raises(ValidationException, match="Insufficient inventory"):
            sale_service.update_sale(
                sale_id,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                [
                    {
                        "product_id": sample_product.id,
                        "quantity": 11,
                        "sell_price": sample_product.sell_price,
                        "profit": 11
                        * (sample_product.sell_price - sample_product.cost_price),
                    }
                ],
            )

    def test_create_sale_emits_sale_added_and_inventory_events_once(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_payloads, sale_handler = capture_signal(event_system.sale_added)
        inventory_payloads, inventory_handler = capture_signal(
            event_system.inventory_changed
        )

        try:
            sale_id = sale_service.create_sale(**sample_sale_data)

            assert sale_payloads == [sale_id]
            assert inventory_payloads == [sample_product.id]
        finally:
            event_system.sale_added.disconnect(sale_handler)
            event_system.inventory_changed.disconnect(inventory_handler)

    def test_delete_sale_emits_sale_deleted_and_inventory_events_once(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        sale_payloads, sale_handler = capture_signal(event_system.sale_deleted)
        inventory_payloads, inventory_handler = capture_signal(
            event_system.inventory_changed
        )

        try:
            sale_service.delete_sale(sale_id)

            assert sale_payloads == [sale_id]
            assert inventory_payloads == [sample_product.id]
        finally:
            event_system.sale_deleted.disconnect(sale_handler)
            event_system.inventory_changed.disconnect(inventory_handler)

    def test_cancel_sale_emits_sale_updated_once(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        sale_payloads, sale_handler = capture_signal(event_system.sale_updated)

        try:
            sale_service.cancel_sale(sale_id)

            assert sale_payloads == [sale_id]
        finally:
            event_system.sale_updated.disconnect(sale_handler)

    def test_update_sale_emits_sale_updated_once(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)
        sale_payloads, sale_handler = capture_signal(event_system.sale_updated)

        try:
            sale_service.update_sale(
                sale_id,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                sample_sale_data["items"],
            )

            assert sale_payloads == [sale_id]
        finally:
            event_system.sale_updated.disconnect(sale_handler)


class TestCancelSale:
    def test_cancel_sale_sets_status_cancelled(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        sale_service.cancel_sale(sale_id)

        sale = sale_service.get_sale(sale_id)
        assert sale.status == "cancelled"

    def test_cancel_sale_reverts_inventory(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        # After create: 10 - 2 = 8
        assert inventory_service.get_inventory(sample_product.id).quantity == 8.0

        sale_service.cancel_sale(sale_id)

        # After cancel: 8 + 2 = 10 (restored)
        assert inventory_service.get_inventory(sample_product.id).quantity == 10.0

    def test_cancel_sale_twice_raises(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        sale_service.cancel_sale(sale_id)

        with pytest.raises(ValidationException):
            sale_service.cancel_sale(sale_id)

    def test_cancel_nonexistent_sale_raises(self, sale_service):
        with pytest.raises(NotFoundException):
            sale_service.cancel_sale(99999)

    def test_delete_nonexistent_sale_raises_not_found(self, sale_service):
        with pytest.raises(NotFoundException):
            sale_service.delete_sale(99999)

    def test_update_nonexistent_sale_raises_not_found(
        self, sale_service, sample_sale_data
    ):
        with pytest.raises(NotFoundException):
            sale_service.update_sale(
                99999,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                sample_sale_data["items"],
            )

    def test_cancel_sale_preserves_record(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        """Cancelled sale remains in DB for audit trail."""
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        sale_service.cancel_sale(sale_id)

        sale = sale_service.get_sale(sale_id)
        assert sale is not None
        assert sale.id == sale_id
        assert len(sale.items) == 1

    def test_delete_cancelled_sale_raises_and_keeps_inventory(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        """Deleting a cancelled sale raises and does not restore inventory twice."""
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        # After create: 10 - 2 = 8
        assert inventory_service.get_inventory(sample_product.id).quantity == 8.0

        sale_service.cancel_sale(sale_id)

        # After cancel: 8 + 2 = 10 (restored)
        assert inventory_service.get_inventory(sample_product.id).quantity == 10.0

        with pytest.raises(ValidationException):
            sale_service.delete_sale(sale_id)

        # Inventory must NOT be restored a second time (still 10, not 12)
        assert inventory_service.get_inventory(sample_product.id).quantity == 10.0

        # The sale row must still exist
        sale = sale_service.get_sale(sale_id)
        assert sale is not None
        assert sale.status == "cancelled"

    def test_update_cancelled_sale_raises(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        """Updating a cancelled sale raises and keeps inventory and status intact."""
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_id = sale_service.create_sale(**sample_sale_data)

        # After create: 10 - 2 = 8
        assert inventory_service.get_inventory(sample_product.id).quantity == 8.0

        sale_service.cancel_sale(sale_id)

        # After cancel: 8 + 2 = 10 (restored)
        assert inventory_service.get_inventory(sample_product.id).quantity == 10.0

        updated_items = [
            {
                "product_id": sample_product.id,
                "quantity": 1,
                "sell_price": sample_product.sell_price,
                "profit": sample_product.sell_price - sample_product.cost_price,
            }
        ]

        with pytest.raises(ValidationException):
            sale_service.update_sale(
                sale_id,
                sample_sale_data["customer_id"],
                sample_sale_data["date"],
                updated_items,
            )

        # Inventory unchanged (still 10, no re-restore and no new deduction)
        assert inventory_service.get_inventory(sample_product.id).quantity == 10.0

        # The sale row must still exist and remain cancelled
        sale = sale_service.get_sale(sale_id)
        assert sale is not None
        assert sale.status == "cancelled"


class TestGetAllSalesPagination:
    def test_pagination_limit(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 30.0)
        for _ in range(5):
            sale_service.create_sale(**sample_sale_data)

        page = sale_service.get_all_sales(limit=2, offset=0)
        assert len(page) == 2

    def test_pagination_offset(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 30.0)
        ids = [sale_service.create_sale(**sample_sale_data) for _ in range(4)]

        page1 = sale_service.get_all_sales(limit=2, offset=0)
        page2 = sale_service.get_all_sales(limit=2, offset=2)

        page1_ids = {s.id for s in page1}
        page2_ids = {s.id for s in page2}
        assert page1_ids.isdisjoint(page2_ids)
        assert page1_ids | page2_ids == set(ids)

    def test_pagination_offset_beyond_total_returns_empty(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        inventory_service.update_quantity(sample_product.id, 10.0)
        sale_service.create_sale(**sample_sale_data)

        page = sale_service.get_all_sales(limit=10, offset=100)
        assert page == []

    def test_pagination_invalid_limit_raises(self, sale_service):
        with pytest.raises(ValidationException):
            sale_service.get_all_sales(limit=0, offset=0)

    def test_pagination_invalid_offset_raises(self, sale_service):
        with pytest.raises(ValidationException):
            sale_service.get_all_sales(limit=10, offset=-1)


class TestCacheFreshness:
    def test_get_all_sales_includes_new_sale(
        self, sale_service, sample_sale_data, inventory_service, sample_product
    ):
        SaleService.clear_cache()
        inventory_service.update_quantity(sample_product.id, 30.0)

        sales_before = sale_service.get_all_sales()
        sale_id = sale_service.create_sale(**sample_sale_data)

        sales_after = sale_service.get_all_sales()
        assert len(sales_after) == len(sales_before) + 1
        assert any(sale.id == sale_id for sale in sales_after)
