import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from services.product_service import ProductService
from ui.purchase_view import PurchaseView


def test_barcode_scan_uses_service_and_opens_item_dialog(qtbot, db_manager, mocker):
    product_id = ProductService().create_product(
        {
            "name": "Producto Escaneo Compra",
            "description": "Prueba escaneo compra",
            "cost_price": 600,
            "sell_price": 1000,
            "barcode": "777777777777",
        }
    )

    view = PurchaseView()
    qtbot.addWidget(view)

    product = view.product_service.get_product(product_id)
    get_by_barcode_mock = mocker.patch.object(
        view.product_service, "get_product_by_barcode", return_value=product
    )

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return False

        def get_item_data(self):
            return {}

    dialog_mock = mocker.patch(
        "ui.purchase_view.PurchaseItemDialog", return_value=FakeDialog()
    )

    view.barcode_input.setText("777777777777")
    view.handle_barcode_scan()

    get_by_barcode_mock.assert_called_once_with("777777777777")
    dialog_mock.assert_called_once()
    assert dialog_mock.call_args[0][0] is product
    assert view.barcode_input.text() == ""
