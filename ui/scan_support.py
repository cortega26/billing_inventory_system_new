from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.styles import DesignTokens

MAX_BARCODE_LENGTH = 14  # EAN-14 is the longest common barcode


def flash_input_error(widget: QWidget) -> None:
    """Flash a widget's background red to signal a failed scan."""
    widget.setStyleSheet(f"background-color: {DesignTokens.COLOR_ERROR_BG};")
    QTimer.singleShot(1000, lambda: widget.setStyleSheet(""))


def on_barcode_length_exceeded(barcode_input) -> None:
    """Clear over-long barcode input (scanner garbling guard)."""
    if len(barcode_input.text()) > MAX_BARCODE_LENGTH:
        barcode_input.clear()


def show_product_selection_dialog[T](
    products: list[T], parent: QWidget | None
) -> T | None:
    """Show a picker for multiple matching products; return the chosen product."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Seleccionar Producto")
    layout = QVBoxLayout(dialog)
    product_list = QComboBox()
    for product in products:
        display_text = f"{product.name}"
        if getattr(product, "barcode", None):
            display_text += f" (Código: {product.barcode})"
        product_list.addItem(display_text, product)
    layout.addWidget(QLabel("Seleccione un producto:"))
    layout.addWidget(product_list)
    button_box = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return product_list.currentData()
    return None
