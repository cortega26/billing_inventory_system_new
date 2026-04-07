import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from services.product_service import ProductService
from ui.inventory_view import InventoryView
from utils.system.event_system import event_system


def capture_signal(signal):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    signal.connect(handler)
    return payloads, handler


def test_edit_inventory_does_not_reemit_inventory_events(qtbot, db_manager, mocker):
    product_id = ProductService().create_product(
        {
            "name": "Producto Inventario UI",
            "description": "Prueba de evento",
            "cost_price": 500,
            "sell_price": 900,
            "barcode": "123456789025",
        }
    )

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return True

        def get_data(self):
            return {"adjustment": 1.5, "reason": "conteo"}

    view = InventoryView()
    qtbot.addWidget(view)
    item = next(entry for entry in view.current_inventory if entry["product_id"] == product_id)

    mocker.patch("ui.inventory_view.EditInventoryDialog", return_value=FakeDialog())
    mocker.patch("ui.inventory_view.show_info_message")

    def update_quantity(*_args, **_kwargs):
        event_system.inventory_changed.emit(product_id)

    update_quantity_mock = mocker.patch.object(
        view.inventory_service,
        "update_quantity",
        side_effect=update_quantity,
    )
    changed_payloads, changed_handler = capture_signal(event_system.inventory_changed)
    updated_payloads, updated_handler = capture_signal(event_system.inventory_updated)

    try:
        view.edit_inventory(item)

        update_quantity_mock.assert_called_once_with(
            product_id=product_id,
            quantity_change=1.5,
        )
        assert changed_payloads == [product_id]
        assert updated_payloads == []
    finally:
        event_system.inventory_changed.disconnect(changed_handler)
        event_system.inventory_updated.disconnect(updated_handler)