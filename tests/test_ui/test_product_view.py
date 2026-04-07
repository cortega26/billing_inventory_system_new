import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton

from services.product_service import ProductService
from ui.product_view import ProductView
from utils.exceptions import DatabaseException
from utils.system.event_system import event_system


def capture_signal(signal):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    signal.connect(handler)
    return payloads, handler


def test_product_action_buttons_reflect_active_status(qtbot, db_manager):
    service = ProductService()
    service.create_product(
        {
            "name": "Test Product",
            "description": "UI test product",
            "cost_price": 500,
            "sell_price": 900,
            "barcode": "123456789012",
        }
    )

    view = ProductView()
    qtbot.addWidget(view)

    assert view.product_table.item(0, 4).text() == "Activo"

    actions_widget = view.product_table.cellWidget(0, 8)
    buttons = actions_widget.findChildren(QPushButton)

    assert [button.text() for button in buttons] == ["Editar", "Eliminar"]
    assert all(button.minimumWidth() == 80 for button in buttons)
    assert all(button.maximumWidth() == 80 for button in buttons)


def test_add_product_does_not_reemit_product_added_event(qtbot, db_manager, mocker):
    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self.product_data = {
                "name": "Producto UI",
                "description": "Alta de prueba",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789020",
                "category_id": None,
            }

        def exec(self):
            return True

    view = ProductView()
    qtbot.addWidget(view)
    mocker.patch("ui.product_view.EditProductDialog", return_value=FakeDialog())
    mocker.patch("ui.product_view.show_info_message")

    def create_product(_data):
        event_system.product_added.emit(201)
        return 201

    mocker.patch.object(view.product_service, "create_product", side_effect=create_product)
    payloads, handler = capture_signal(event_system.product_added)

    try:
        view.add_product()

        assert payloads == [201]
    finally:
        event_system.product_added.disconnect(handler)


def test_edit_product_does_not_reemit_product_updated_event(
    qtbot, db_manager, mocker
):
    service = ProductService()
    product_id = service.create_product(
        {
            "name": "Producto Editar",
            "description": "Antes",
            "cost_price": 500,
            "sell_price": 900,
            "barcode": "123456789021",
        }
    )
    product = service.get_product(product_id)

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self.product_data = {
                "name": "Producto Editado",
                "description": "Después",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789021",
                "category_id": product.category_id,
            }

        def exec(self):
            return True

    view = ProductView()
    qtbot.addWidget(view)
    mocker.patch("ui.product_view.EditProductDialog", return_value=FakeDialog())
    mocker.patch("ui.product_view.show_info_message")

    def update_product(*_args, **_kwargs):
        event_system.product_updated.emit(product_id)

    mocker.patch.object(view.product_service, "update_product", side_effect=update_product)
    payloads, handler = capture_signal(event_system.product_updated)

    try:
        view.edit_product(product)

        assert payloads == [product_id]
    finally:
        event_system.product_updated.disconnect(handler)


def test_delete_product_does_not_reemit_product_deleted_event(
    qtbot, db_manager, mocker
):
    service = ProductService()
    product_id = service.create_product(
        {
            "name": "Producto Eliminar",
            "description": "Archivo",
            "cost_price": 500,
            "sell_price": 900,
            "barcode": "123456789022",
        }
    )
    product = service.get_product(product_id)

    view = ProductView()
    qtbot.addWidget(view)
    mocker.patch("ui.product_view.show_info_message")
    mocker.patch(
        "ui.product_view.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    )

    def delete_product(_product_id):
        event_system.product_deleted.emit(_product_id)

    mocker.patch.object(view.product_service, "delete_product", side_effect=delete_product)
    payloads, handler = capture_signal(event_system.product_deleted)

    try:
        view.delete_product(product)

        assert payloads == [product_id]
    finally:
        event_system.product_deleted.disconnect(handler)


def test_show_context_menu_handles_missing_product_from_service(
    qtbot, db_manager, mocker
):
    service = ProductService()
    service.create_product(
        {
            "name": "Producto Contextual",
            "description": "Fila para menú",
            "cost_price": 500,
            "sell_price": 900,
            "barcode": "123456789023",
        }
    )

    view = ProductView()
    qtbot.addWidget(view)
    mocker.patch.object(view.product_service, "get_product", return_value=None)
    show_error = mocker.patch("ui.product_view.show_error_message")

    position = view.product_table.visualItemRect(view.product_table.item(0, 0)).center()
    view.show_context_menu(position)

    show_error.assert_called_once_with("Error", "Error al mostrar el menú contextual")


def test_add_product_shows_single_error_dialog_for_service_failure(
    qtbot, db_manager, mocker
):
    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self.product_data = {
                "name": "Producto UI con error",
                "description": "Alta fallida",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789024",
                "category_id": None,
            }

        def exec(self):
            return True

    view = ProductView()
    qtbot.addWidget(view)
    mocker.patch("ui.product_view.EditProductDialog", return_value=FakeDialog())
    show_error_dialog = mocker.patch("utils.decorators.show_error_dialog")
    mocker.patch.object(
        view.product_service,
        "create_product",
        side_effect=DatabaseException("fallo controlado de producto"),
    )

    with pytest.raises(DatabaseException, match="fallo controlado de producto"):
        view.add_product()

    show_error_dialog.assert_called_once()
    args = show_error_dialog.call_args.args
    assert args[0] == "Operation Failed"
    assert "fallo controlado de producto" in args[1]
    assert args[2] is view
