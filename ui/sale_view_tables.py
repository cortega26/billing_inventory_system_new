from typing import Any, Callable, Dict, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QWidget

from models.customer import Customer
from models.sale import Sale
from utils.helpers import format_price
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem


RemoveSaleItemHandler = Callable[[int], None]
SaleActionHandler = Callable[[Optional[Sale]], None]


def render_sale_item_row(
    table: QTableWidget,
    row: int,
    item: Dict[str, Any],
    remove_handler: RemoveSaleItemHandler,
) -> None:
    """Render one current-sale row with stable formatting and actions."""
    table.setItem(row, 0, NumericTableWidgetItem(item["product_id"]))
    table.setItem(row, 1, QTableWidgetItem(item["product_name"]))

    quantity_item = NumericTableWidgetItem(round(item["quantity"], 3))
    quantity_item.setTextAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    table.setItem(row, 2, quantity_item)
    table.setItem(row, 3, PriceTableWidgetItem(item["sell_price"], format_price))

    total = int(round(item["quantity"] * item["sell_price"]))
    table.setItem(row, 4, PriceTableWidgetItem(total, format_price))
    table.setCellWidget(row, 5, _build_remove_action_widget(row, remove_handler))
    table.setRowHeight(row, 36)


def update_sale_total_label(
    total_label: QLabel,
    sale_items: Sequence[Dict[str, Any]],
) -> None:
    """Update the total label for the current sale using CLP rounding rules."""
    total_amount = sum(
        int(round(item["quantity"] * item["sell_price"])) for item in sale_items
    )
    total_label.setText(f"Total: {format_price(total_amount)}")


def render_sale_history_row(
    table: QTableWidget,
    row: int,
    sale: Sale,
    customer: Optional[Customer],
    on_view: SaleActionHandler,
    on_edit: SaleActionHandler,
    on_print: SaleActionHandler,
    on_delete: SaleActionHandler,
) -> None:
    """Render one historical sale row and its action buttons."""
    table.setItem(row, 0, NumericTableWidgetItem(sale.id))

    if customer is not None:
        table.setItem(row, 1, QTableWidgetItem(customer.identifier_9))
        table.setItem(row, 2, QTableWidgetItem(customer.identifier_3or4 or "N/A"))
        table.setItem(row, 3, QTableWidgetItem(customer.name or ""))
    else:
        table.setItem(row, 1, QTableWidgetItem("Eliminado"))
        table.setItem(row, 2, QTableWidgetItem("N/A"))
        table.setItem(row, 3, QTableWidgetItem("Cliente eliminado"))

    date_item = QTableWidgetItem(sale.date.strftime("%Y-%m-%d"))
    date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    table.setItem(row, 4, date_item)
    table.setItem(row, 5, PriceTableWidgetItem(sale.total_amount, format_price))
    table.setItem(row, 6, PriceTableWidgetItem(sale.total_profit, format_price))

    receipt_item = QTableWidgetItem(sale.receipt_id or "")
    receipt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    table.setItem(row, 7, receipt_item)
    table.setCellWidget(
        row,
        8,
        _build_sale_history_actions_widget(
            sale,
            on_view,
            on_edit,
            on_print,
            on_delete,
        ),
    )
    table.setRowHeight(row, 36)


def _build_remove_action_widget(
    row: int,
    remove_handler: RemoveSaleItemHandler,
) -> QWidget:
    actions_widget = QWidget()
    actions_layout = QHBoxLayout(actions_widget)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    remove_button = QPushButton("Eliminar")
    remove_button.setFixedWidth(80)
    remove_button.setStyleSheet("padding: 2px 8px;")
    remove_button.clicked.connect(lambda: remove_handler(row))
    actions_layout.addWidget(remove_button)
    return actions_widget


def _build_sale_history_actions_widget(
    sale: Sale,
    on_view: SaleActionHandler,
    on_edit: SaleActionHandler,
    on_print: SaleActionHandler,
    on_delete: SaleActionHandler,
) -> QWidget:
    actions_widget = QWidget()
    actions_layout = QHBoxLayout(actions_widget)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(4)
    actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    button_specs = [
        ("👁", on_view, "View sale details"),
        ("✏", on_edit, "Edit sale"),
        ("🖨", on_print, "Print receipt"),
        ("🗑", on_delete, "Delete this sale"),
    ]
    for label, handler, tooltip in button_specs:
        button = QPushButton(label)
        button.clicked.connect(lambda _, current_handler=handler: current_handler(sale))
        button.setToolTip(tooltip)
        button.setFixedWidth(36)
        button.setStyleSheet("padding: 2px 4px;")
        actions_layout.addWidget(button)

    return actions_widget