from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QLineEdit

from ui.analytics_view import AnalyticsView


def test_show_category_performance_populates_summary_and_chart_contract(qtbot, mocker):
    summary_text = QLineEdit()
    qtbot.addWidget(summary_text)

    populate_mock = mocker.Mock()
    analytics_service = SimpleNamespace(
        get_category_performance=mocker.Mock(
            return_value=[
                {
                    "category": "Abarrotes",
                    "total_sales": 15000,
                    "number_of_products_sold": 12.5,
                    "sale_count": 4,
                },
                {
                    "category": "Bebidas",
                    "total_sales": 5000,
                    "number_of_products_sold": 3.0,
                    "sale_count": 1,
                },
            ]
        )
    )
    view = SimpleNamespace(
        analytics_service=analytics_service,
        _populate_table_and_chart=populate_mock,
        summary_text=summary_text,
    )

    AnalyticsView.show_category_performance(view, "2026-04-01", "2026-04-07")

    analytics_service.get_category_performance.assert_called_once_with(
        "2026-04-01", "2026-04-07"
    )
    populate_mock.assert_called_once_with(
        data=[
            {
                "category": "Abarrotes",
                "total_sales": 15000,
                "number_of_products_sold": 12.5,
                "sale_count": 4,
            },
            {
                "category": "Bebidas",
                "total_sales": 5000,
                "number_of_products_sold": 3.0,
                "sale_count": 1,
            },
        ],
        headers=["Categoría", "Ventas Totales", "Productos Vendidos"],
        keys=["category", "total_sales", "number_of_products_sold"],
        x_key="category",
        y_key="total_sales",
        title="Rendimiento por Categoría",
        chart_type="bar",
    )
    assert summary_text.text() == "Ventas totales: $20000, Productos vendidos: 15.5"


def test_show_top_selling_products_populates_summary_and_chart_contract(qtbot, mocker):
    summary_text = QLineEdit()
    qtbot.addWidget(summary_text)

    populate_mock = mocker.Mock()
    analytics_service = SimpleNamespace(
        get_top_selling_products=mocker.Mock(
            return_value=[
                {
                    "id": 7,
                    "product_id": 7,
                    "name": "Arroz",
                    "total_quantity": 4.5,
                    "total_revenue": 5400,
                    "sale_count": 2,
                },
                {
                    "id": 8,
                    "product_id": 8,
                    "name": "Aceite",
                    "total_quantity": 3.0,
                    "total_revenue": 3600,
                    "sale_count": 1,
                },
            ]
        )
    )
    view = SimpleNamespace(
        analytics_service=analytics_service,
        _populate_table_and_chart=populate_mock,
        summary_text=summary_text,
    )

    AnalyticsView.show_top_selling_products(view, "2026-04-01", "2026-04-07", 5)

    analytics_service.get_top_selling_products.assert_called_once_with(
        "2026-04-01", "2026-04-07", 5
    )
    populate_mock.assert_called_once_with(
        data=[
            {
                "id": 7,
                "product_id": 7,
                "name": "Arroz",
                "total_quantity": 4.5,
                "total_revenue": 5400,
                "sale_count": 2,
            },
            {
                "id": 8,
                "product_id": 8,
                "name": "Aceite",
                "total_quantity": 3.0,
                "total_revenue": 3600,
                "sale_count": 1,
            },
        ],
        headers=["ID Producto", "Producto", "Cantidad Total", "Ingresos Totales"],
        keys=["product_id", "name", "total_quantity", "total_revenue"],
        x_key="name",
        y_key="total_quantity",
        title="Productos Más Vendidos",
        chart_type="bar",
    )
    assert summary_text.text() == "Cantidad total vendida: 7.5, Ingresos totales: $9000"


def test_show_sales_by_weekday_populates_summary_and_chart_contract(qtbot, mocker):
    summary_text = QLineEdit()
    qtbot.addWidget(summary_text)

    populate_mock = mocker.Mock()
    analytics_service = SimpleNamespace(
        get_sales_by_weekday=mocker.Mock(
            return_value=[
                {"weekday": "Monday", "total_sales": 1200, "sale_count": 3},
                {"weekday": "Tuesday", "total_sales": 800, "sale_count": 2},
                {"weekday": "Wednesday", "total_sales": 1000, "sale_count": 1},
            ]
        )
    )
    view = SimpleNamespace(
        analytics_service=analytics_service,
        _populate_table_and_chart=populate_mock,
        summary_text=summary_text,
    )

    AnalyticsView.show_sales_by_weekday(view, "2026-04-01", "2026-04-07")

    analytics_service.get_sales_by_weekday.assert_called_once_with(
        "2026-04-01", "2026-04-07"
    )
    populate_mock.assert_called_once_with(
        data=[
            {"weekday": "Monday", "total_sales": 1200, "sale_count": 3},
            {"weekday": "Tuesday", "total_sales": 800, "sale_count": 2},
            {"weekday": "Wednesday", "total_sales": 1000, "sale_count": 1},
        ],
        headers=["Día", "Ventas Totales"],
        keys=["weekday", "total_sales"],
        x_key="weekday",
        y_key="total_sales",
        title="Ventas por Día de la Semana",
        chart_type="bar",
    )
    assert summary_text.text() == "Ventas totales: 3.000, Promedio diario: 0"
