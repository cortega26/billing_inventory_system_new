import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton

from services.customer_service import CustomerService
from ui.customer_view import CustomerView
from utils.system.event_system import event_system


class StubLineEdit:
    def __init__(self, value):
        self._value = value

    def text(self):
        return self._value


def capture_signal(signal):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    signal.connect(handler)
    return payloads, handler


def test_customer_action_buttons_use_wider_fixed_width(qtbot, db_manager):
    service = CustomerService()
    service.create_customer("923456789", "Test Customer")

    view = CustomerView()
    qtbot.addWidget(view)

    assert view.customer_table.item(0, 4).text() == "Activo"

    actions_widget = view.customer_table.cellWidget(0, 7)
    buttons = actions_widget.findChildren(QPushButton)

    assert [button.text() for button in buttons] == ["Editar", "Eliminar"]
    assert all(button.minimumWidth() == 80 for button in buttons)
    assert all(button.maximumWidth() == 80 for button in buttons)
    assert all(button.minimumHeight() == 24 for button in buttons)
    assert all(button.maximumHeight() == 24 for button in buttons)


def test_add_customer_does_not_reemit_customer_added_event(qtbot, db_manager, mocker):
    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self.identifier_9_input = StubLineEdit("923456780")
            self.name_input = StubLineEdit("Nuevo Cliente")
            self.identifier_3or4_input = StubLineEdit("123")

        def exec(self):
            return True

    view = CustomerView()
    qtbot.addWidget(view)
    mocker.patch("ui.customer_view.EditCustomerDialog", return_value=FakeDialog())
    mocker.patch("ui.customer_view.show_info_message")

    def create_customer(*_args, **_kwargs):
        event_system.customer_added.emit(101)
        return 101

    mocker.patch.object(view.customer_service, "create_customer", side_effect=create_customer)
    payloads, handler = capture_signal(event_system.customer_added)

    try:
        view.add_customer()

        assert payloads == [101]
    finally:
        event_system.customer_added.disconnect(handler)


def test_edit_customer_does_not_reemit_customer_updated_event(
    qtbot, db_manager, mocker
):
    service = CustomerService()
    customer_id = service.create_customer("923456781", "Cliente Editar", "321")
    customer = service.get_customer(customer_id)

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self.identifier_9_input = StubLineEdit("923456781")
            self.name_input = StubLineEdit("Cliente Editado")
            self.identifier_3or4_input = StubLineEdit("321")

        def exec(self):
            return True

    view = CustomerView()
    qtbot.addWidget(view)
    mocker.patch("ui.customer_view.EditCustomerDialog", return_value=FakeDialog())
    mocker.patch("ui.customer_view.show_info_message")

    def update_customer(*_args, **_kwargs):
        event_system.customer_updated.emit(customer_id)

    mocker.patch.object(view.customer_service, "update_customer", side_effect=update_customer)
    payloads, handler = capture_signal(event_system.customer_updated)

    try:
        view.edit_customer(customer)

        assert payloads == [customer_id]
    finally:
        event_system.customer_updated.disconnect(handler)


def test_delete_customer_does_not_reemit_customer_deleted_event(
    qtbot, db_manager, mocker
):
    service = CustomerService()
    customer_id = service.create_customer("923456782", "Cliente Eliminar")
    customer = service.get_customer(customer_id)

    view = CustomerView()
    qtbot.addWidget(view)
    mocker.patch("ui.customer_view.show_info_message")
    mocker.patch(
        "ui.customer_view.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    )

    def delete_customer(_customer_id):
        event_system.customer_deleted.emit(_customer_id)

    mocker.patch.object(view.customer_service, "delete_customer", side_effect=delete_customer)
    payloads, handler = capture_signal(event_system.customer_deleted)

    try:
        view.delete_customer(customer)

        assert payloads == [customer_id]
    finally:
        event_system.customer_deleted.disconnect(handler)
