import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QRadioButton

from config import config
from ui.business_selector_dialog import BusinessSelectorDialog

pytest.importorskip("PySide6", reason="PySide6 not installed")


@pytest.fixture
def two_businesses():
    config.set(
        "businesses",
        [
            {"id": "default", "name": "Principal", "db_filename": "billing_inventory.db"},
            {"id": "casabea", "name": "CasaBea", "db_filename": "casabea.db"},
        ],
    )
    config.set("active_business", "default")
    yield


def test_should_show_false_with_single_business(qtbot):
    assert BusinessSelectorDialog.should_show() is False


def test_should_show_true_with_multiple_businesses(qtbot, two_businesses):
    assert BusinessSelectorDialog.should_show() is True


def test_dialog_shows_configured_businesses(qtbot, two_businesses):
    dialog = BusinessSelectorDialog()
    qtbot.addWidget(dialog)

    radios = dialog.findChildren(QRadioButton)
    labels = [radio.text() for radio in radios]
    assert len(radios) == 2
    assert any("Principal" in label for label in labels)
    assert any("CasaBea" in label for label in labels)
    # Active business is preselected
    assert dialog.radio_buttons["default"].isChecked()


def test_accept_persists_selection_when_remembered(qtbot, two_businesses):
    dialog = BusinessSelectorDialog()
    qtbot.addWidget(dialog)

    dialog.radio_buttons["casabea"].setChecked(True)
    dialog.remember_checkbox.setChecked(True)
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)

    assert dialog.result() == 1  # Accepted
    assert dialog.selected_business_id == "casabea"
    assert dialog.remember_selection is True
    assert config.get("active_business") == "casabea"


def test_accept_applies_selection_without_persisting(qtbot, two_businesses):
    dialog = BusinessSelectorDialog()
    qtbot.addWidget(dialog)

    dialog.radio_buttons["casabea"].setChecked(True)
    dialog.remember_checkbox.setChecked(False)
    qtbot.mouseClick(dialog.btn_accept, Qt.MouseButton.LeftButton)

    assert dialog.result() == 1  # Accepted
    assert dialog.selected_business_id == "casabea"
    assert dialog.remember_selection is False
    # Session-only: applied in memory, not persisted to disk
    assert config.get("active_business") == "casabea"
    config.reload()
    assert config.get("active_business") == "default"


def test_cancel_rejects(qtbot, two_businesses):
    dialog = BusinessSelectorDialog()
    qtbot.addWidget(dialog)

    qtbot.mouseClick(dialog.btn_cancel, Qt.MouseButton.LeftButton)

    assert dialog.result() == 0  # Rejected
