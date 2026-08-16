from unittest.mock import MagicMock, patch

import pytest

from database.database_manager import DatabaseManager
from services.audit_service import AuditService
from services.category_service import CategoryService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.purchase_service import PurchaseService
from services.sale_service import SaleService
from utils.exceptions import ValidationException


class TestInventoryServiceUpdates:
    @patch("services.inventory_service.InventoryService.update_quantity")
    def test_apply_batch_updates_sales(self, mock_update):
        # Items as dicts
        items = [{"product_id": 1, "quantity": 2.0}, {"product_id": 2, "quantity": 1.5}]

        InventoryService.apply_batch_updates(items, multiplier=-1.0)

        # Should call update_quantity twice with negative values
        assert mock_update.call_count == 2
        mock_update.assert_any_call(1, -2.0)
        mock_update.assert_any_call(2, -1.5)

    @patch("services.inventory_service.InventoryService.update_quantity")
    def test_apply_batch_updates_purchases(self, mock_update):
        # Items as objects (mocked)
        item1 = MagicMock()
        item1.product_id = 10
        item1.quantity = 5.0

        items = [item1]

        InventoryService.apply_batch_updates(items, multiplier=1.0)

        mock_update.assert_called_once_with(10, 5.0)

    @patch("services.inventory_service.InventoryService.update_quantity")
    def test_apply_batch_updates_revert_sale(self, mock_update):
        # Revert sale means adding back to inventory -> multiplier 1.0 (since items are positive qty)
        items = [{"product_id": 1, "quantity": 2.0}]

        InventoryService.apply_batch_updates(items, multiplier=1.0)

        mock_update.assert_called_once_with(1, 2.0)

    def test_apply_batch_updates_invalid_item(self):
        # Should skip or error? Code says log warning and continue.
        items = [{"invalid": "data"}]
        # Should not raise
        InventoryService.apply_batch_updates(items)

    @patch("services.inventory_service.InventoryService.update_quantity")
    def test_apply_batch_updates_with_emit_events_false(self, mock_update):
        InventoryService.apply_batch_updates(
            [{"product_id": 3, "quantity": 4.0}], emit_events=False
        )

        mock_update.assert_called_once_with(3, 4.0, emit_events=False)

    def test_apply_batch_updates_invalid_multiplier_raises_validation(self):
        with pytest.raises(ValidationException, match="multiplier must be 1.0"):
            InventoryService.apply_batch_updates([], multiplier=0.0)

    def test_normalize_batch_item_supports_dict_and_object(self):
        item = MagicMock()
        item.product_id = 9
        item.quantity = 1.25

        assert InventoryService._normalize_batch_item(
            {"product_id": 5, "quantity": 2.5}
        ) == (5, 2.5)
        assert InventoryService._normalize_batch_item(item) == (9, 1.25)


class TestInventoryServiceRealDb:
    """Real-database guard tests for the inventory service.

    Uses the `db_manager` fixture (real in-memory DB) and exercises the
    guards that the dispatch tests above only mock: negative-stock
    rejection, the CREATE branch, quantity precision, the
    set_quantity/adjust_inventory trails, and the read-only inventory
    queries.
    """

    @pytest.fixture(autouse=True)
    def setup(self, db_manager):
        self.inventory_service = InventoryService()
        self.category_service = CategoryService()
        self.product_service = ProductService()
        self.customer_service = CustomerService()
        self.sale_service = SaleService()
        self.purchase_service = PurchaseService()
        self.cat_id = self.category_service.create_category("Test Cat")
        self.prod_id = self.product_service.create_product(
            {
                "name": "Inv Test Product",
                "category_id": self.cat_id,
                "cost_price": 1000,
                "sell_price": 2000,
            }
        )

    def _quantity(self) -> float:
        return self.inventory_service.get_inventory(self.prod_id).quantity

    def _adjustment_rows(self) -> list[dict]:
        return DatabaseManager.fetch_all(
            "SELECT * FROM inventory_adjustments WHERE product_id = ?",
            (self.prod_id,),
        )

    def test_update_quantity_rejects_negative_and_preserves_quantity(self):
        assert self._quantity() == 0.0

        with pytest.raises(ValidationException, match="cannot be negative"):
            self.inventory_service.update_quantity(self.prod_id, -1.0)

        assert self._quantity() == 0.0

    def test_update_quantity_creates_missing_inventory_row(self):
        DatabaseManager.execute_query(
            "DELETE FROM inventory WHERE product_id = ?", (self.prod_id,)
        )
        assert self.inventory_service.get_inventory(self.prod_id) is None

        self.inventory_service.update_quantity(self.prod_id, 5.0)

        inventory = self.inventory_service.get_inventory(self.prod_id)
        assert inventory is not None
        assert inventory.quantity == 5.0

    def test_update_quantity_rejects_input_with_more_than_three_decimals(self):
        with pytest.raises(ValidationException, match="more than 3 decimal places"):
            self.inventory_service.update_quantity(self.prod_id, 0.123456)

        assert self._quantity() == 0.0

    def test_update_quantity_rounds_float_artifacts_to_three_decimals(self):
        self.inventory_service.update_quantity(self.prod_id, 0.1)
        self.inventory_service.update_quantity(self.prod_id, 0.2)

        raw = DatabaseManager.fetch_one(
            "SELECT quantity FROM inventory WHERE product_id = ?", (self.prod_id,)
        )
        assert raw["quantity"] == 0.3

    def test_set_quantity_writes_adjustment_and_audit_rows(self):
        self.inventory_service.set_quantity(self.prod_id, 10.0)

        assert self._quantity() == 10.0
        rows = self._adjustment_rows()
        assert len(rows) == 1
        assert rows[0]["quantity_change"] == 10.0
        assert rows[0]["reason"] == "manual_set"
        assert (
            len(
                AuditService.get_entries(
                    entity_type="inventory", operation="set_inventory"
                )
            )
            == 1
        )

        # Setting the same value again pins the 0-change adjustment row.
        self.inventory_service.set_quantity(self.prod_id, 10.0)

        rows = self._adjustment_rows()
        assert len(rows) == 2
        assert rows[1]["quantity_change"] == 0.0

    def test_adjust_inventory_happy_path(self):
        self.inventory_service.adjust_inventory(self.prod_id, 2.0, "stock count")

        assert self._quantity() == 2.0
        rows = self._adjustment_rows()
        assert len(rows) == 1
        assert rows[0]["quantity_change"] == 2.0
        assert rows[0]["reason"] == "stock count"
        assert (
            len(
                AuditService.get_entries(
                    entity_type="inventory", operation="adjust_inventory"
                )
            )
            == 1
        )

    def test_adjust_inventory_below_zero_raises_and_leaves_no_trace(self):
        self.inventory_service.adjust_inventory(self.prod_id, 2.0, "stock count")

        with pytest.raises(ValidationException, match="cannot be negative"):
            self.inventory_service.adjust_inventory(self.prod_id, -999.0, "shrinkage")

        assert self._quantity() == 2.0
        assert len(self._adjustment_rows()) == 1
        assert (
            len(
                AuditService.get_entries(
                    entity_type="inventory", operation="adjust_inventory"
                )
            )
            == 1
        )

    def test_get_inventory_value(self):
        self.inventory_service.set_quantity(self.prod_id, 5.0)

        assert self.inventory_service.get_inventory_value() == 5000  # 5 * cost 1000

    def test_get_inventory_movements(self):
        self.purchase_service.create_purchase(
            "Supplier",
            "2026-07-05",
            [{"product_id": self.prod_id, "quantity": 2.0, "cost_price": 1000}],
        )
        cust_id = self.customer_service.create_customer("923456789", "Test Customer")
        self.sale_service.create_sale(
            cust_id,
            "2026-07-10",
            [
                {
                    "product_id": self.prod_id,
                    "quantity": 2.0,
                    "sell_price": 2000,
                    "profit": 2000,
                }
            ],
        )

        movements = self.inventory_service.get_inventory_movements(
            self.prod_id, "2026-07-01", "2026-07-31"
        )

        assert [(m["type"], m["quantity_change"], m["reason"]) for m in movements] == [
            ("purchase", 2.0, "Purchase"),
            ("sale", -2.0, "Sale"),
        ]

    def test_get_inventory_turnover(self):
        self.inventory_service.set_quantity(self.prod_id, 10.0)
        cust_id = self.customer_service.create_customer("923456789", "Test Customer")
        self.sale_service.create_sale(
            cust_id,
            "2026-07-15",
            [
                {
                    "product_id": self.prod_id,
                    "quantity": 2.0,
                    "sell_price": 2000,
                    "profit": 2000,
                }
            ],
        )

        # 2 sold / 8 remaining after the sale.
        assert self.inventory_service.get_inventory_turnover(
            "2026-07-01", "2026-07-31"
        ) == {self.prod_id: 0.25}
