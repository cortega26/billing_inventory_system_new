from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QWidget,
)

from ui.scan_support import (
    flash_input_error,
    on_barcode_length_exceeded,
    show_product_selection_dialog,
)

pytest.importorskip("PySide6", reason="PySide6 not installed")


def test_on_barcode_length_exceeded_clears_overlong_input(qtbot):
    barcode_input = QLineEdit()
    qtbot.addWidget(barcode_input)
    barcode_input.setText("1" * 20)

    on_barcode_length_exceeded(barcode_input)

    assert barcode_input.text() == ""


def test_on_barcode_length_exceeded_keeps_max_length_input(qtbot):
    barcode_input = QLineEdit()
    qtbot.addWidget(barcode_input)
    barcode_input.setText("1" * 14)

    on_barcode_length_exceeded(barcode_input)

    assert barcode_input.text() == "1" * 14


def test_flash_input_error_sets_then_resets_stylesheet(qtbot, mocker):
    widget = QWidget()
    qtbot.addWidget(widget)

    reset_callbacks = []
    mocker.patch(
        "ui.scan_support.QTimer.singleShot",
        side_effect=lambda ms, callback: reset_callbacks.append(callback),
    )

    flash_input_error(widget)

    assert "background-color" in widget.styleSheet()

    reset_callbacks[0]()
    assert widget.styleSheet() == ""


def _selection_dialog() -> QDialog:
    return next(
        widget
        for widget in QApplication.topLevelWidgets()
        if isinstance(widget, QDialog)
        and widget.windowTitle() == "Seleccionar Producto"
    )


def test_show_product_selection_dialog_returns_selected_product_on_ok(qtbot, mocker):
    products = [
        SimpleNamespace(name="Pan", barcode="111"),
        SimpleNamespace(name="Leche", barcode="222"),
    ]

    def fake_exec():
        combo = _selection_dialog().findChild(QComboBox)
        combo.setCurrentIndex(1)
        button_box = _selection_dialog().findChild(QDialogButtonBox)
        button_box.button(QDialogButtonBox.StandardButton.Ok).click()
        return QDialog.DialogCode.Accepted

    mocker.patch("ui.scan_support.QDialog.exec", side_effect=fake_exec)
    result = show_product_selection_dialog(products, None)

    assert result is products[1]


def test_show_product_selection_dialog_uses_normalized_barcode_label(qtbot, mocker):
    products = [SimpleNamespace(name="Pan", barcode="111")]
    captured_text = []

    def fake_exec():
        combo = _selection_dialog().findChild(QComboBox)
        captured_text.append(combo.itemText(0))
        button_box = _selection_dialog().findChild(QDialogButtonBox)
        button_box.button(QDialogButtonBox.StandardButton.Ok).click()
        return QDialog.DialogCode.Accepted

    mocker.patch("ui.scan_support.QDialog.exec", side_effect=fake_exec)
    result = show_product_selection_dialog(products, None)

    assert result is products[0]
    assert captured_text[0] == "Pan (Código: 111)"
    assert "Código de Barras:" not in captured_text[0]


def test_show_product_selection_dialog_returns_none_on_cancel(qtbot, mocker):
    products = [SimpleNamespace(name="Pan", barcode="111")]

    def fake_exec():
        button_box = _selection_dialog().findChild(QDialogButtonBox)
        button_box.button(QDialogButtonBox.StandardButton.Cancel).click()
        return QDialog.DialogCode.Rejected

    mocker.patch("ui.scan_support.QDialog.exec", side_effect=fake_exec)
    result = show_product_selection_dialog(products, None)

    assert result is None
