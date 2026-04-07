from datetime import datetime

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QLabel, QPushButton

from models.sale import Sale
from ui.sale_view_tables import (
    render_sale_history_row,
    render_sale_item_row,
    update_sale_total_label,
)
from utils.helpers import create_table, format_price


def test_render_sale_item_row_populates_cells_and_remove_action(qtbot):
    table = create_table(["ID", "Producto", "Cantidad", "Precio", "Total", "Acciones"])
    qtbot.addWidget(table)
    table.setRowCount(1)
    removed_rows = []

    render_sale_item_row(
        table,
        0,
        {
            "product_id": 7,
            "product_name": "Arroz",
            "quantity": 2.5,
            "sell_price": 1200,
        },
        removed_rows.append,
    )

    assert table.item(0, 0).text() == "7"
    assert table.item(0, 1).text() == "Arroz"
    assert table.item(0, 4).text() == format_price(3000)
    remove_button = table.cellWidget(0, 5).findChild(QPushButton)
    assert remove_button.text() == "Eliminar"

    remove_button.click()

    assert removed_rows == [0]


def test_update_sale_total_label_uses_clp_rounding():
    total_label = QLabel()

    update_sale_total_label(
        total_label,
        [
            {"quantity": 1.234, "sell_price": 1000},
            {"quantity": 2.0, "sell_price": 501},
        ],
    )

    assert total_label.text() == f"Total: {format_price(2236)}"


def test_render_sale_history_row_handles_deleted_customer_and_action_buttons(qtbot):
    table = create_table(
        [
            "ID",
            "N° Celular",
            "N° Departamento",
            "Nombre Cliente",
            "Fecha",
            "Monto Total",
            "Ganancia",
            "Recibo ID",
            "Acciones",
        ]
    )
    qtbot.addWidget(table)
    table.setRowCount(1)
    calls = []
    sale = Sale(
        id=5,
        customer_id=None,
        date=datetime(2026, 4, 7),
        total_amount=3500,
        total_profit=900,
        receipt_id="R-5",
    )

    render_sale_history_row(
        table,
        0,
        sale,
        None,
        lambda current_sale: calls.append(("view", current_sale.id)),
        lambda current_sale: calls.append(("edit", current_sale.id)),
        lambda current_sale: calls.append(("print", current_sale.id)),
        lambda current_sale: calls.append(("delete", current_sale.id)),
    )

    assert table.item(0, 1).text() == "Eliminado"
    assert table.item(0, 2).text() == "N/A"
    assert table.item(0, 3).text() == "Cliente eliminado"
    assert table.item(0, 5).text() == format_price(3500)

    buttons = table.cellWidget(0, 8).findChildren(QPushButton)
    assert [button.text() for button in buttons] == ["👁", "✏", "🖨", "🗑"]

    buttons[0].click()
    buttons[3].click()

    assert calls == [("view", 5), ("delete", 5)]