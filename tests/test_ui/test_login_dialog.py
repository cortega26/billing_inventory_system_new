import pytest
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from config import config
from ui.login_dialog import LoginDialog, hash_pin, is_legacy_hash, verify_pin

pytest.importorskip("PySide6", reason="PySide6 not installed")

TEST_SALT = bytes.fromhex("00" * 16)


def test_hash_pin_pbkdf2_roundtrip():
    stored = hash_pin("1234", salt=TEST_SALT)
    assert stored.startswith("pbkdf2$600000$")
    assert verify_pin(stored, "1234")
    assert not verify_pin(stored, "4321")
    assert not verify_pin(stored, "99999")


def test_legacy_hash_is_rejected():
    legacy = "a" * 64
    assert is_legacy_hash(legacy)
    assert not verify_pin(legacy, "1234")


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

    # Click accept and verify config is updated with a PBKDF2 hash
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog.result() == 1  # Accepted
    stored = config.get("pin_hash")
    assert stored.startswith("pbkdf2$600000$")
    assert verify_pin(stored, "1234")


def test_login_dialog_login_mode_success(qtbot):
    # Set pin_hash in config
    stored = hash_pin("9876", salt=TEST_SALT)
    config.set("pin_hash", stored)
    config.save()

    dialog = LoginDialog()
    qtbot.addWidget(dialog)

    assert dialog.pin_hash == stored
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
    assert config.get("pin_failed_attempts") == 0
    assert config.get("pin_locked_until") == ""


def test_login_dialog_rejects_legacy_hash(qtbot):
    # A legacy single-round SHA-256 hash must be rejected with a clear message
    config.set("pin_hash", "a" * 64)
    config.save()

    dialog = LoginDialog()
    qtbot.addWidget(dialog)

    dialog.pin_input.setText("1234")
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog.result() == 0  # Rejected
    assert "formato antiguo" in dialog.msg_label.text()


def test_login_dialog_login_mode_failed_attempts(qtbot, mocker):
    config.set("pin_hash", hash_pin("9876", salt=TEST_SALT))
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
    assert config.get("pin_failed_attempts") == 5
    locked_until = config.get("pin_locked_until")
    assert locked_until != ""
    assert datetime.fromisoformat(locked_until) > datetime.now()


def test_login_dialog_persistent_lockout_blocks_new_instance(qtbot, mocker):
    config.set("pin_hash", hash_pin("9876", salt=TEST_SALT))
    config.save()
    mocker.patch.object(
        QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok
    )

    dialog1 = LoginDialog()
    qtbot.addWidget(dialog1)
    for _ in range(5):
        dialog1.pin_input.setText("1111")
        qtbot.mouseClick(dialog1.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog1.result() == 0  # Locked and rejected
    assert config.get("pin_failed_attempts") == 5
    assert datetime.fromisoformat(config.get("pin_locked_until")) > datetime.now()

    # A brand-new dialog instance is still blocked by the persisted lockout
    dialog2 = LoginDialog()
    qtbot.addWidget(dialog2)
    assert dialog2.attempts == 5
    dialog2.pin_input.setText("9876")
    qtbot.mouseClick(dialog2.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog2.result() == 0  # Rejected without incrementing
    assert "bloqueado" in dialog2.msg_label.text().lower()
    assert config.get("pin_failed_attempts") == 5


def test_login_dialog_lockout_expires(qtbot):
    config.set("pin_hash", hash_pin("9876", salt=TEST_SALT))
    config.set("pin_failed_attempts", 5)
    config.set(
        "pin_locked_until",
        (datetime.now() - timedelta(minutes=1)).isoformat(),
    )
    config.save()

    dialog = LoginDialog()
    qtbot.addWidget(dialog)
    assert dialog.attempts == 5

    dialog.pin_input.setText("9876")
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)
    assert dialog.result() == 1  # Accepted
    assert config.get("pin_failed_attempts") == 0
    assert config.get("pin_locked_until") == ""
