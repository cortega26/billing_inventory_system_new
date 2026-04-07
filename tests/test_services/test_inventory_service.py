from unittest.mock import MagicMock, patch

import pytest

from services.inventory_service import InventoryService
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
