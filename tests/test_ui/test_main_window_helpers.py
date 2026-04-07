import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from ui.main_window import (
    AUDIT_TAB,
    CUSTOMER_REFRESH_TARGETS,
    PRODUCT_REFRESH_TARGETS,
    PURCHASE_REFRESH_TARGETS,
    MainWindow,
    build_backup_skipped_status_message,
)
from utils.system.event_system import event_system


@pytest.fixture
def allow_main_window_close(mocker):
    return mocker.patch(
        "ui.main_window.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    )


def test_build_backup_skipped_status_message_low_disk_space():
    payload = {"reason": "low_disk_space", "backup_dir": "/tmp/backups"}

    message = build_backup_skipped_status_message(payload)

    assert "espacio insuficiente" in message


def test_build_backup_skipped_status_message_generic():
    message = build_backup_skipped_status_message({"reason": "other"})

    assert message == "Alerta: copia de seguridad omitida"


def test_main_window_includes_audit_tab(qtbot, db_manager, allow_main_window_close):
    window = MainWindow()
    qtbot.addWidget(window)

    tab_names = [window.tab_widget.tabText(index) for index in range(window.tab_widget.count())]

    assert "Auditoría" in tab_names


def test_main_window_refreshes_once_for_customer_add(
    qtbot, db_manager, mocker, allow_main_window_close
):
    class StubLineEdit:
        def __init__(self, value):
            self._value = value

        def text(self):
            return self._value

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self.identifier_9_input = StubLineEdit("923456783")
            self.name_input = StubLineEdit("Cliente Ventana")
            self.identifier_3or4_input = StubLineEdit("555")

        def exec(self):
            return True

    window = MainWindow()
    qtbot.addWidget(window)
    customer_view = window.tab_widget.widget(1)
    refresh_spy = mocker.patch.object(window, "refresh_relevant_views")

    mocker.patch("ui.customer_view.EditCustomerDialog", return_value=FakeDialog())
    mocker.patch("ui.customer_view.show_info_message")

    def create_customer(*_args, **_kwargs):
        event_system.customer_added.emit(301)
        return 301

    mocker.patch.object(customer_view.customer_service, "create_customer", side_effect=create_customer)

    customer_view.add_customer()

    refresh_spy.assert_called_once_with(CUSTOMER_REFRESH_TARGETS)


def test_main_window_refreshes_once_for_product_add(
    qtbot, db_manager, mocker, allow_main_window_close
):
    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self.product_data = {
                "name": "Producto Ventana",
                "description": "Alta",
                "cost_price": 500,
                "sell_price": 900,
                "barcode": "123456789023",
                "category_id": None,
            }

        def exec(self):
            return True

    window = MainWindow()
    qtbot.addWidget(window)
    product_view = window.tab_widget.widget(2)
    refresh_spy = mocker.patch.object(window, "refresh_relevant_views")

    mocker.patch("ui.product_view.EditProductDialog", return_value=FakeDialog())
    mocker.patch("ui.product_view.show_info_message")

    def create_product(_data):
        event_system.product_added.emit(302)
        return 302

    mocker.patch.object(product_view.product_service, "create_product", side_effect=create_product)

    product_view.add_product()

    refresh_spy.assert_called_once_with(PRODUCT_REFRESH_TARGETS)


def test_main_window_refreshes_once_for_purchase_create(
    qtbot, db_manager, mocker, allow_main_window_close
):
    window = MainWindow()
    qtbot.addWidget(window)
    purchase_view = window.tab_widget.widget(4)
    refresh_spy = mocker.patch.object(window, "refresh_relevant_views")

    purchase_view.supplier_input.setText("Proveedor Ventana")
    purchase_view.purchase_items = [
        {"product_id": 1, "product_name": "Item", "quantity": 1, "cost_price": 500}
    ]
    mocker.patch("ui.purchase_view.show_info_message")

    def create_purchase(*_args, **_kwargs):
        event_system.purchase_added.emit(303)
        return 303

    mocker.patch.object(purchase_view.purchase_service, "create_purchase", side_effect=create_purchase)

    purchase_view.complete_purchase()

    refresh_spy.assert_called_once_with(PURCHASE_REFRESH_TARGETS)


def test_refresh_relevant_views_only_refreshes_requested_tabs(
    qtbot, db_manager, mocker, allow_main_window_close
):
    window = MainWindow()
    qtbot.addWidget(window)

    refresh_spies = {}
    for tab_name, widget in window.views_by_name.items():
        refresh_spies[tab_name] = mocker.patch.object(widget, "refresh")

    window.refresh_relevant_views(("Productos", AUDIT_TAB))

    assert refresh_spies["Productos"].call_count == 1
    assert refresh_spies[AUDIT_TAB].call_count == 1

    for tab_name, spy in refresh_spies.items():
        if tab_name not in {"Productos", AUDIT_TAB}:
            assert spy.call_count == 0


def test_purchase_view_delete_does_not_reemit_purchase_deleted_event(
    qtbot, db_manager, mocker, allow_main_window_close
):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    event_system.purchase_deleted.connect(handler)

    try:
        window = MainWindow()
        qtbot.addWidget(window)
        purchase_view = window.tab_widget.widget(4)
        mocker.patch("ui.purchase_view.show_info_message")
        mocker.patch(
            "ui.purchase_view.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        )

        def delete_purchase(_purchase_id):
            event_system.purchase_deleted.emit(_purchase_id)

        mocker.patch.object(purchase_view.purchase_service, "delete_purchase", side_effect=delete_purchase)

        purchase_view.delete_purchase(SimpleNamespace(id=304))

        assert payloads == [304]
    finally:
        event_system.purchase_deleted.disconnect(handler)
