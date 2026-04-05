import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QPushButton

from services.customer_service import CustomerService
from ui.customer_view import CustomerView


def test_customer_action_buttons_use_wider_fixed_width(qtbot, db_manager):
    service = CustomerService()
    service.create_customer("923456789", "Test Customer")

    view = CustomerView()
    qtbot.addWidget(view)

    actions_widget = view.customer_table.cellWidget(0, 6)
    buttons = actions_widget.findChildren(QPushButton)

    assert [button.text() for button in buttons] == ["Editar", "Eliminar"]
    assert all(button.minimumWidth() == 80 for button in buttons)
    assert all(button.maximumWidth() == 80 for button in buttons)
    assert all(button.minimumHeight() == 24 for button in buttons)
    assert all(button.maximumHeight() == 24 for button in buttons)
