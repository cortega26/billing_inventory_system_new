import pytest

from models.enums import MAX_PRICE_CLP, MAX_PURCHASE_ITEMS, MAX_SALE_ITEMS
from utils.exceptions import ValidationException
from utils.validation.item_validators import validate_item_count, validate_line_item


def _sale_item(**overrides):
    item = {"product_id": 1, "quantity": 1.0, "sell_price": 100}
    item.update(overrides)
    return item


def _purchase_item(**overrides):
    item = {"product_id": 1, "quantity": 1.0, "cost_price": 100}
    item.update(overrides)
    return item


class TestValidateLineItem:
    def test_sale_item_above_max_price_accepted(self):
        # Sale line items intentionally have NO price cap (documented divergence)
        item = _sale_item(sell_price=2_000_000)
        validate_line_item(
            item,
            quantity_min=0.001,
            quantity_max=None,
            price_min=1,
            price_max=None,
            price_key="sell_price",
        )
        assert item["sell_price"] == 2_000_000

    def test_purchase_item_above_max_price_rejected(self):
        item = _purchase_item(cost_price=MAX_PRICE_CLP + 1)
        with pytest.raises(ValidationException):
            validate_line_item(
                item,
                quantity_min=0.001,
                quantity_max=9999999.999,
                price_min=0,
                price_max=MAX_PRICE_CLP,
                price_key="cost_price",
            )

    def test_sale_item_excess_quantity_precision_rejected(self):
        item = _sale_item(quantity=1.2345)
        with pytest.raises(ValidationException, match="decimal places"):
            validate_line_item(
                item,
                quantity_min=0.001,
                quantity_max=None,
                price_min=1,
                price_max=None,
                price_key="sell_price",
            )

    def test_purchase_item_excess_quantity_precision_rejected(self):
        item = _purchase_item(quantity=1.2345)
        with pytest.raises(ValidationException, match="decimal places"):
            validate_line_item(
                item,
                quantity_min=0.001,
                quantity_max=9999999.999,
                price_min=0,
                price_max=MAX_PRICE_CLP,
                price_key="cost_price",
            )

    def test_invalid_product_id_rejected(self):
        item = _sale_item(product_id=0)
        with pytest.raises(ValidationException, match="Invalid product ID"):
            validate_line_item(
                item,
                quantity_min=0.001,
                quantity_max=None,
                price_min=1,
                price_max=None,
                price_key="sell_price",
            )

    def test_normalizes_quantity_and_price(self):
        item = _sale_item(quantity="2", sell_price="300")
        validate_line_item(
            item,
            quantity_min=0.001,
            quantity_max=None,
            price_min=1,
            price_max=None,
            price_key="sell_price",
        )
        assert item["quantity"] == 2.0
        assert item["sell_price"] == 300


class TestValidateItemCount:
    def test_empty_list_rejected(self):
        with pytest.raises(ValidationException, match="at least one item"):
            validate_item_count([], MAX_SALE_ITEMS, "sale")

    def test_over_long_list_rejected(self):
        items = [{"product_id": 1, "quantity": 1, "sell_price": 100}] * (
            MAX_PURCHASE_ITEMS + 1
        )
        with pytest.raises(ValidationException, match="Too many items"):
            validate_item_count(items, MAX_PURCHASE_ITEMS, "purchase")

    def test_valid_list_accepted(self):
        items = [{"product_id": 1, "quantity": 1, "sell_price": 100}]
        validate_item_count(items, MAX_SALE_ITEMS, "sale")
