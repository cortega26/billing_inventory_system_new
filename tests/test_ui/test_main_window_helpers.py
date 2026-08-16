import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from config import config
from ui.business_selector_dialog import BusinessSelectorDialog
from ui.main_window import (
    AUDIT_TAB,
    CUSTOMER_REFRESH_TARGETS,
    INVENTORY_REFRESH_TARGETS,
    PRODUCT_REFRESH_TARGETS,
    PURCHASE_REFRESH_TARGETS,
    SALE_REFRESH_TARGETS,
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


@pytest.fixture
def two_businesses():
    config.set(
        "businesses",
        [
            {
                "id": "default",
                "name": "Principal",
                "db_filename": "billing_inventory.db",
            },
            {"id": "casabea", "name": "CasaBea", "db_filename": "casabea.db"},
        ],
    )
    config.set("active_business", "default")
    yield


def build_window_without_tabs(mocker, qtbot, allow_main_window_close):
    """Build MainWindow skipping the DB-bound tab creation.

    Tab creation opens the business database; in CI/worktrees that path can
    fail on sqlite file resolution, and the menu tests don't need the tabs.
    """
    mocker.patch.object(MainWindow, "create_tabs")
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def file_menu_actions(window):
    file_menu = window.menuBar().actions()[0].menu()
    return [action.text() for action in file_menu.actions()]


def test_change_business_action_present_with_two_businesses(
    qtbot, db_manager, mocker, allow_main_window_close, two_businesses
):
    window = build_window_without_tabs(mocker, qtbot, allow_main_window_close)

    assert any("Cambiar de negocio" in text for text in file_menu_actions(window))


def test_change_business_action_hidden_with_single_business(
    qtbot, db_manager, mocker, allow_main_window_close
):
    window = build_window_without_tabs(mocker, qtbot, allow_main_window_close)

    assert not any("Cambiar de negocio" in text for text in file_menu_actions(window))


def test_change_business_handler_shows_restart_message(
    qtbot, db_manager, mocker, allow_main_window_close, two_businesses
):
    window = build_window_without_tabs(mocker, qtbot, allow_main_window_close)
    info_spy = mocker.patch("ui.main_window.show_info_message")
    exec_mock = mocker.patch.object(
        BusinessSelectorDialog, "exec", return_value=QDialog.DialogCode.Accepted
    )

    window.change_business()

    exec_mock.assert_called_once()
    info_spy.assert_called_once_with(
        "Negocio", "El cambio de negocio se aplicará al reiniciar la aplicación."
    )


def test_change_business_handler_informs_single_business_install(
    qtbot, db_manager, mocker, allow_main_window_close
):
    window = build_window_without_tabs(mocker, qtbot, allow_main_window_close)
    info_spy = mocker.patch("ui.main_window.show_info_message")
    exec_mock = mocker.patch.object(
        BusinessSelectorDialog, "exec", return_value=QDialog.DialogCode.Accepted
    )

    window.change_business()

    exec_mock.assert_not_called()
    info_spy.assert_called_once_with("Información", "Solo hay un negocio configurado.")


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

    tab_names = [
        window.tab_widget.tabText(index) for index in range(window.tab_widget.count())
    ]

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

    mocker.patch.object(
        customer_view.customer_service, "create_customer", side_effect=create_customer
    )

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

    mocker.patch.object(
        product_view.product_service, "create_product", side_effect=create_product
    )

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

    mocker.patch.object(
        purchase_view.purchase_service, "create_purchase", side_effect=create_purchase
    )

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
    QApplication.processEvents()  # coalesced refresh is deferred by one event-loop pass

    assert refresh_spies["Productos"].call_count == 1
    assert refresh_spies[AUDIT_TAB].call_count == 1

    for tab_name, spy in refresh_spies.items():
        if tab_name not in {"Productos", AUDIT_TAB}:
            assert spy.call_count == 0


def test_multiple_signals_in_one_pass_refresh_each_tab_once(
    qtbot, db_manager, mocker, allow_main_window_close
):
    window = MainWindow()
    qtbot.addWidget(window)

    refresh_spies = {}
    for tab_name, widget in window.views_by_name.items():
        refresh_spies[tab_name] = mocker.patch.object(widget, "refresh")

    event_system.inventory_changed.emit(1)
    event_system.inventory_changed.emit(2)
    event_system.sale_added.emit(3)

    QApplication.processEvents()

    affected_tabs = set(SALE_REFRESH_TARGETS) | set(INVENTORY_REFRESH_TARGETS)
    for tab_name in affected_tabs:
        assert refresh_spies[tab_name].call_count == 1
    for tab_name in set(window.views_by_name) - affected_tabs:
        assert refresh_spies[tab_name].call_count == 0

    event_system.inventory_changed.emit(4)
    QApplication.processEvents()

    for tab_name in INVENTORY_REFRESH_TARGETS:
        assert refresh_spies[tab_name].call_count == 2
    for tab_name in affected_tabs - set(INVENTORY_REFRESH_TARGETS):
        assert refresh_spies[tab_name].call_count == 1


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

        mocker.patch.object(
            purchase_view.purchase_service,
            "delete_purchase",
            side_effect=delete_purchase,
        )

        purchase_view.delete_purchase(SimpleNamespace(id=304))

        assert payloads == [304]
    finally:
        event_system.purchase_deleted.disconnect(handler)
