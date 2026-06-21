import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from config import APP_NAME, COMPANY_NAME
from services.product_service import ProductService
from services.inventory_service import InventoryService
from services.category_service import CategoryService
from ui.sale_view import SaleView

pytest.importorskip("PySide6", reason="PySide6 not installed")


def test_quick_scan_checkbox_persistence(qtbot, db_manager):
    # Clear settings first
    settings = QSettings(COMPANY_NAME, APP_NAME)
    settings.remove("QuickScanEnabled")

    # Create view, check default value
    view1 = SaleView()
    qtbot.addWidget(view1)
    assert not view1.quick_scan_checkbox.isChecked()

    # Toggle the checkbox
    view1.quick_scan_checkbox.setChecked(True)
    assert settings.value("QuickScanEnabled", type=bool) is True

    # Create a new view, check that it loads the persisted value
    view2 = SaleView()
    qtbot.addWidget(view2)
    assert view2.quick_scan_checkbox.isChecked()

    # Clean up settings
    settings.remove("QuickScanEnabled")


def test_non_blocking_low_stock_warning(qtbot, db_manager, mocker):
    # Setup database with a category, product, and low stock
    cat_service = CategoryService()
    cat_id = cat_service.create_category("Test Category")

    prod_service = ProductService()
    p_id = prod_service.create_product({
        "name": "Low Stock Cookie",
        "barcode": "88888888",
        "category_id": cat_id,
        "sell_price": 500,
        "cost_price": 250,
        "stock_quantity": 0,
    })

    inv_service = InventoryService()
    inv_service.set_quantity(p_id, 3.0)  # low stock (3 < 10)

    view = SaleView()
    qtbot.addWidget(view)

    # Enable quick scan
    view.quick_scan_checkbox.setChecked(True)

    # Mock the barcode input and call handle_barcode_scan
    view.barcode_input.setText("88888888")

    # Mock show_status_message on parent window if needed
    mock_main_window = mocker.MagicMock()
    mock_main_window.show_status_message = mocker.MagicMock()
    mocker.patch.object(view, "window", return_value=mock_main_window)

    # Ensure QMessageBox.warning is NOT called
    mock_msg_box = mocker.patch("ui.sale_view.QMessageBox.warning")

    view.handle_barcode_scan()

    # Verify warning label is shown
    assert not view.scan_warning_label.isHidden()
    assert "Low Stock Cookie" in view.scan_warning_label.text()
    assert "Disponible: 3" in view.scan_warning_label.text()

    # Verify QMessageBox was never used
    mock_msg_box.assert_not_called()

    # Verify main window status bar received the warning message
    mock_main_window.show_status_message.assert_called_once()
    assert "Low Stock Cookie" in mock_main_window.show_status_message.call_args[0][0]


def test_table_keypress_event_filter(qtbot, db_manager, mocker):
    view = SaleView()
    qtbot.addWidget(view)

    # Mock adjustment and void methods
    mock_void = mocker.patch.object(view, "void_selected_item")
    mock_adjust = mocker.patch.object(view, "adjust_selected_quantity")

    # Send Delete key to self.sale_items_table via event filter
    event_del = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    view.eventFilter(view.sale_items_table, event_del)
    mock_void.assert_called_once()

    # Send Plus key
    event_plus = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.NoModifier)
    view.eventFilter(view.sale_items_table, event_plus)
    mock_adjust.assert_called_with(1)

    # Send Minus key
    event_minus = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier)
    view.eventFilter(view.sale_items_table, event_minus)
    mock_adjust.assert_called_with(-1)
