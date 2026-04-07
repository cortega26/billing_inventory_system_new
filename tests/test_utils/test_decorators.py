import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QWidget

from utils.decorators import handle_exceptions
from utils.exceptions import DatabaseException


class ServiceProbe:
    @handle_exceptions(DatabaseException, show_dialog=True)
    def explode(self):
        raise DatabaseException("fallo de servicio")


class WidgetProbe(QWidget):
    @handle_exceptions(DatabaseException, show_dialog=True)
    def explode(self):
        raise DatabaseException("fallo de UI")


def test_handle_exceptions_skips_dialog_for_non_ui_instances(mocker):
    show_error_dialog = mocker.patch("utils.decorators.show_error_dialog")

    with pytest.raises(DatabaseException, match="fallo de servicio"):
        ServiceProbe().explode()

    show_error_dialog.assert_not_called()


def test_handle_exceptions_shows_dialog_for_widgets(qtbot, mocker):
    show_error_dialog = mocker.patch("utils.decorators.show_error_dialog")
    widget = WidgetProbe()
    qtbot.addWidget(widget)

    with pytest.raises(DatabaseException, match="fallo de UI"):
        widget.explode()

    show_error_dialog.assert_called_once_with(
        "Operation Failed", "fallo de UI", widget
    )