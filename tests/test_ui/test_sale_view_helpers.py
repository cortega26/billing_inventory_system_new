from types import SimpleNamespace

import pytest

from types import SimpleNamespace

from ui.sale_view import build_customer_display, build_shortcuts_help_text
from ui.sale_view_support import (
    build_quick_scan_item_data,
    build_selected_customer_text,
    prepare_processed_sale_items,
    resolve_customer_by_identifier,
)
from utils.exceptions import ValidationException


def test_build_customer_display_with_full_customer_data():
    customer = SimpleNamespace(
        identifier_9="912345678",
        identifier_3or4="1234",
        name="Ana",
    )

    assert build_customer_display(customer) == "912345678 (1234) - Ana"


def test_build_customer_display_with_deleted_customer():
    assert build_customer_display(None) == "Cliente eliminado"


def test_build_shortcuts_help_text_contains_primary_shortcuts():
    text = build_shortcuts_help_text()

    assert "Ctrl+B" in text
    assert "Ctrl+Enter" in text
    assert "F1" in text


def test_build_selected_customer_text_uses_cashier_facing_order():
    customer = SimpleNamespace(
        identifier_9="912345678",
        identifier_3or4="1234",
        name="Ana",
    )

    assert build_selected_customer_text(customer) == "1234 - Ana - 912345678"


def test_resolve_customer_by_identifier_deduplicates_short_matches_before_choosing():
    shared_customer = SimpleNamespace(
        id=1,
        identifier_9="912345678",
        identifier_3or4="1234",
        name="Ana",
    )
    other_customer = SimpleNamespace(
        id=2,
        identifier_9="998887776",
        identifier_3or4="1234",
        name="Beto",
    )

    chooser_calls = []

    class CustomerServiceStub:
        @staticmethod
        def get_customer_by_identifier_9(_identifier):
            return None

        @staticmethod
        def get_customers_by_identifier_3or4(_identifier):
            return [shared_customer, shared_customer, other_customer]

    def chooser(customers):
        chooser_calls.append(customers)
        return customers[1]

    customer = resolve_customer_by_identifier("1234", CustomerServiceStub(), chooser)

    assert customer is other_customer
    assert chooser_calls == [[shared_customer, other_customer]]


def test_resolve_customer_by_identifier_rejects_invalid_lengths():
    with pytest.raises(ValidationException, match="3/4-digit or 9-digit"):
        resolve_customer_by_identifier("12", object(), lambda _customers: None)


def test_prepare_processed_sale_items_normalizes_types_for_service_calls():
    processed_items = prepare_processed_sale_items(
        [
            {
                "product_id": "7",
                "product_name": 900,
                "quantity": 1.2349,
                "sell_price": "1500",
                "profit": "300",
            }
        ]
    )

    assert processed_items == [
        {
            "product_id": 7,
            "product_name": "900",
            "quantity": 1.235,
            "sell_price": 1500,
            "profit": 300,
        }
    ]


def test_build_quick_scan_item_data_uses_default_quantity_and_profit():
    product = SimpleNamespace(
        id=9,
        name="Arroz",
        sell_price=1200,
        cost_price=800,
    )

    item_data = build_quick_scan_item_data(product)

    assert item_data == {
        "product_id": 9,
        "product_name": "Arroz",
        "quantity": 1.0,
        "sell_price": 1200,
        "profit": 400,
    }
