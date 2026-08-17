import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from utils.helpers import wait_cursor
from utils.ui.table_items import action_button, build_actions_cell


def test_build_actions_cell_centers_buttons_with_zero_margins(qtbot):
    button = QPushButton("Eliminar")
    cell = build_actions_cell(button)
    qtbot.addWidget(cell)

    assert isinstance(cell, QWidget)
    layout = cell.layout()
    assert layout.contentsMargins().left() == 0
    assert layout.contentsMargins().top() == 0
    assert layout.contentsMargins().right() == 0
    assert layout.contentsMargins().bottom() == 0
    assert layout.alignment() == Qt.AlignmentFlag.AlignCenter
    assert layout.count() == 1
    assert layout.itemAt(0).widget() is button


def test_build_actions_cell_respects_spacing_and_multiple_buttons(qtbot):
    first = QPushButton("Ver")
    second = QPushButton("Eliminar")
    cell = build_actions_cell(first, second, spacing=4)
    qtbot.addWidget(cell)

    layout = cell.layout()
    assert layout.spacing() == 4
    assert layout.count() == 2
    assert layout.itemAt(1).widget() is second


def test_action_button_emits_handler_on_click(qtbot):
    calls = []
    button = action_button("Eliminar", lambda: calls.append(1))
    qtbot.addWidget(button)

    assert button.text() == "Eliminar"
    assert button.minimumWidth() == 80 and button.maximumWidth() == 80
    button.click()

    assert calls == [1]


def test_action_button_respects_width_height_and_style(qtbot):
    button = action_button(
        "Ver", lambda: None, width=36, height=24, style="padding: 2px 4px;"
    )
    qtbot.addWidget(button)

    assert button.minimumWidth() == 36 and button.maximumWidth() == 36
    assert button.minimumHeight() == 24 and button.maximumHeight() == 24
    assert "padding: 2px 4px;" in button.styleSheet()


def test_wait_cursor_restores_prior_cursor(qtbot):
    app = QApplication.instance()
    app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        with wait_cursor():
            assert app.overrideCursor() is not None
        assert app.overrideCursor() is not None
    finally:
        app.restoreOverrideCursor()
    assert app.overrideCursor() is None


def test_wait_cursor_restores_on_exception(qtbot):
    app = QApplication.instance()
    with pytest.raises(RuntimeError), wait_cursor():
        raise RuntimeError("boom")
    assert app.overrideCursor() is None
