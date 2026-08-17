from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QWidget

from models.customer import Customer
from models.sale import Sale
from utils.helpers import format_price
from utils.math.financial_calculator import FinancialCalculator
from utils.ui.table_items import (
    NumericTableWidgetItem,
    PriceTableWidgetItem,
    action_button,
    build_actions_cell,
)

RemoveSaleItemHandler = Callable[[int], None]
SaleActionHandler = Callable[[Sale | None], None]


def render_sale_item_row(
    table: QTableWidget,
    row: int,
    item: dict[str, Any],
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

    total = FinancialCalculator.calculate_item_total(
        item["quantity"], item["sell_price"]
    )
    table.setItem(row, 4, PriceTableWidgetItem(total, format_price))
    table.setCellWidget(row, 5, _build_remove_action_widget(row, remove_handler))
    table.setRowHeight(row, 36)


def update_sale_total_label(
    total_label: QLabel,
    sale_items: Sequence[dict[str, Any]],
) -> None:
    """Update the total label for the current sale using CLP rounding rules."""
    total_amount = sum(
        FinancialCalculator.calculate_item_total(item["quantity"], item["sell_price"])
        for item in sale_items
    )
    total_label.setText(f"Total: {format_price(total_amount)}")


def render_sale_history_row(
    table: QTableWidget,
    row: int,
    sale: Sale,
    customer: Customer | None,
    on_view: SaleActionHandler,
    on_edit: SaleActionHandler,
    on_print: SaleActionHandler,
    on_delete: SaleActionHandler,
) -> None:
    """Render one historical sale row and its action buttons."""
    assert sale.id is not None
    table.setItem(row, 0, NumericTableWidgetItem(sale.id))

    if customer is not None:
        table.setItem(row, 1, QTableWidgetItem(customer.identifier_9))
        table.setItem(row, 2, QTableWidgetItem(customer.identifier_3or4 or "N/A"))
        table.setItem(row, 3, QTableWidgetItem(customer.name or ""))
    else:
        table.setItem(row, 1, QTableWidgetItem("Eliminado"))
        table.setItem(row, 2, QTableWidgetItem("N/A"))
        table.setItem(row, 3, QTableWidgetItem("Cliente eliminado"))

    date_item = QTableWidgetItem(
        sale.date.strftime("%Y-%m-%d") if sale.date is not None else ""
    )
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
    remove_button = action_button("Eliminar", lambda: remove_handler(row))
    return build_actions_cell(remove_button)


def _build_sale_history_actions_widget(
    sale: Sale,
    on_view: SaleActionHandler,
    on_edit: SaleActionHandler,
    on_print: SaleActionHandler,
    on_delete: SaleActionHandler,
) -> QWidget:
    button_specs = [
        ("👁", on_view, "Ver detalle de venta"),
        ("✏", on_edit, "Editar venta"),
        ("🖨", on_print, "Imprimir recibo"),
        ("🗑", on_delete, "Eliminar venta"),
    ]
    buttons = []
    for label, handler, tooltip in button_specs:
        button = action_button(
            label,
            lambda _, current_handler=handler: current_handler(sale),
            width=36,
            style="padding: 2px 4px;",
        )
        button.setToolTip(tooltip)
        buttons.append(button)
    return build_actions_cell(*buttons, spacing=4)
