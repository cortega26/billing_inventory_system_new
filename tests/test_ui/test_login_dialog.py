import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from config import config
from ui.login_dialog import LoginDialog, hash_pin

pytest.importorskip("PySide6", reason="PySide6 not installed")


def test_login_dialog_setup_mode(qtbot):
    # pin_hash is empty in config by default
    assert config.get("pin_hash") == ""

    dialog = LoginDialog()
    qtbot.addWidget(dialog)

    # Accept button should be disabled initially
    assert not dialog.btn_accept.isEnabled()

    # Enter invalid PIN (non-digit)
    dialog.pin_input.setText("abcd")
    dialog.confirm_input.setText("abcd")
    assert not dialog.btn_accept.isEnabled()
    assert dialog.msg_label.text() == "El PIN debe contener solo números"

    # Enter invalid PIN (too short)
    dialog.pin_input.setText("12")
    dialog.confirm_input.setText("12")
    assert not dialog.btn_accept.isEnabled()
    assert dialog.msg_label.text() == "El PIN debe tener entre 4 y 6 dígitos"

    # Enter non-matching PINs
    dialog.pin_input.setText("1234")
    dialog.confirm_input.setText("1235")
    assert not dialog.btn_accept.isEnabled()
    assert dialog.msg_label.text() == "Los PINs no coinciden"

    # Enter valid matching PINs
    dialog.pin_input.setText("1234")
    dialog.confirm_input.setText("1234")
    assert dialog.btn_accept.isEnabled()
    assert dialog.msg_label.text() == ""

    # Click accept and verify config is updated
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog.result() == 1  # Accepted
    assert config.get("pin_hash") == hash_pin("1234")


def test_login_dialog_login_mode_success(qtbot):
    # Set pin_hash in config
    config.set("pin_hash", hash_pin("9876"))
    config.save()

    dialog = LoginDialog()
    qtbot.addWidget(dialog)

    assert dialog.pin_hash == hash_pin("9876")
    assert not dialog.btn_accept.isEnabled()

    # Invalid inputs
    dialog.pin_input.setText("98a")
    assert not dialog.btn_accept.isEnabled()

    # Valid but incorrect PIN (won't accept yet until clicked/submitted)
    dialog.pin_input.setText("1234")
    assert dialog.btn_accept.isEnabled()

    # Correct PIN
    dialog.pin_input.setText("9876")
    assert dialog.btn_accept.isEnabled()

    # Accept
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog.result() == 1  # Accepted


def test_login_dialog_login_mode_failed_attempts(qtbot, mocker):
    config.set("pin_hash", hash_pin("9876"))
    config.save()

    dialog = LoginDialog()
    qtbot.addWidget(dialog)

    # Mock QMessageBox to prevent blocking execution
    mocker.patch.object(
        QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok
    )

    # Attempt 1: wrong PIN
    dialog.pin_input.setText("1111")
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog.attempts == 1
    assert "incorrecto" in dialog.msg_label.text()

    # Attempt 2, 3, 4
    for i in range(2, 5):
        dialog.pin_input.setText("1111")
        qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
        assert dialog.attempts == i

    # Attempt 5: should lock and reject
    dialog.pin_input.setText("1111")
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog.attempts == 5
    assert dialog.result() == 0  # Rejected
    QMessageBox.critical.assert_called_once()
