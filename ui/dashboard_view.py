from datetime import datetime, timedelta
from math import ceil
from typing import Callable, Union

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import QDate, QMargins, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from utils.helpers import create_table, format_price
from utils.ui.table_items import NumericTableWidgetItem

from services.analytics_service import AnalyticsService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.purchase_service import PurchaseService
from services.sale_service import SaleService
from utils.decorators import ui_operation
from utils.exceptions import UIException
from utils.system.event_system import event_system
from utils.system.logger import logger


class MetricWidget(QFrame):
    def __init__(self, label: str, value_func: Callable[[], Union[str, int, float]]):
        super().__init__()
        self.value_func = value_func
        self.setFrameShape(QFrame.Shape.Box)
        # Global stylesheet handles default QFrame border/radius now if we used QFrame class,
        # but to ensure it looks like a card we can keep specific style or move to class.
        # Let's use a class property for cleaner separation
        self.setProperty("class", "card")

        layout = QVBoxLayout(self)
        self.label_widget = QLabel(label)
        self.label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_widget = QLabel()
        self.value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Increase font size for value
        font = self.value_widget.font()
        font.setPointSize(16)
        font.setBold(True)
        self.value_widget.setFont(font)

        layout.addWidget(self.label_widget)
        layout.addWidget(self.value_widget)

        self.update_value()
        self.setup_event_connections()

    def setup_event_connections(self):
        event_system.sale_added.connect(self.update_value)
        event_system.purchase_added.connect(self.update_value)
        event_system.inventory_changed.connect(self.update_value)

    @ui_operation()
    def update_value(self, *args):
        value = self.value_func()
        self.value_widget.setText(str(value))


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self.sale_service = SaleService()
        self.purchase_service = PurchaseService()
        self.inventory_service = InventoryService()
        self.customer_service = CustomerService()
        self.analytics_service = AnalyticsService()

        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=28)  # Last 4 weeks

        logger.debug("Dashboard view initialized")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top row with key metrics
        metrics_layout = QHBoxLayout()
        metrics_layout.addWidget(MetricWidget("Ventas Totales", self.get_total_sales))
        metrics_layout.addWidget(MetricWidget("Ganancia Total", self.get_total_profits))
        metrics_layout.addWidget(
            MetricWidget("Valor Inventario", self.get_inventory_value)
        )
        metrics_layout.addWidget(MetricWidget("Margen Ganancia", self.get_profit_margin))
        metrics_layout.addWidget(MetricWidget("Ventas de Hoy", self.get_todays_sales))
        layout.addLayout(metrics_layout)

        # Middle row: Charts
        self.charts_layout = QHBoxLayout()
        self.profit_trend_chart_view = self.create_profit_trend_chart()
        self.top_products_chart_view = self.create_top_products_chart()

        # Set fixed size policies for both charts
        self.profit_trend_chart_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.top_products_chart_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Add charts to the layout with a 1:1 ratio
        self.charts_layout.addWidget(self.profit_trend_chart_view, 1)
        self.charts_layout.addWidget(self.top_products_chart_view, 1)



        layout.addLayout(self.charts_layout)

        # Bottom row: Low Stock Alerts
        low_stock_layout = QVBoxLayout()
        low_stock_label = QLabel("Alerta Stock Bajo (< 10 unidades)")
        low_stock_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        low_stock_layout.addWidget(low_stock_label)

        self.low_stock_table = create_table(["ID", "Producto", "Cantidad"])
        self.low_stock_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.low_stock_table.setMinimumHeight(150)
        low_stock_layout.addWidget(self.low_stock_table)
        
        layout.addLayout(low_stock_layout)

        self.setLayout(layout)
        
        # Initial load of low stock
        self.update_low_stock()

    def update_dashboard(self):
        try:
            # Update metrics
            for widget in self.findChildren(MetricWidget):
                if isinstance(widget, MetricWidget):
                    widget.update_value()

            # Recreate charts
            new_profit_trend_chart = self.create_profit_trend_chart()
            new_top_products_chart = self.create_top_products_chart()

            # Replace old charts
            self.charts_layout.replaceWidget(
                self.profit_trend_chart_view, new_profit_trend_chart
            )
            self.charts_layout.replaceWidget(
                self.top_products_chart_view, new_top_products_chart
            )

            self.profit_trend_chart_view.deleteLater()
            self.top_products_chart_view.deleteLater()

            self.profit_trend_chart_view = new_profit_trend_chart
            self.top_products_chart_view = new_top_products_chart



            # Update low stock
            self.update_low_stock()

            logger.info("Dashboard updated successfully")
        except Exception as e:
            logger.error("Failed to update dashboard", extra={"error": str(e)})
            raise UIException(f"Dashboard update failed: {str(e)}")

    def refresh(self):
        try:
            self.update_dashboard()
            logger.debug("Dashboard refresh completed")
        except Exception as e:
            logger.error("Dashboard refresh failed", extra={"error": str(e)})

    @ui_operation()
    def get_total_sales(self) -> str:
        total_sales_value = self.sale_service.get_total_sales(
            self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
        )
        return f"${total_sales_value:,.0f}".replace(",", ".")

    @ui_operation()
    def get_total_profits(self) -> str:
        total_profits_value = self.sale_service.get_total_profits(
            self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
        )
        return f"${total_profits_value:,.0f}".replace(",", ".")

    @ui_operation()
    def get_inventory_value(self) -> str:
        inv_value = self.inventory_service.get_inventory_value()
        return f"${inv_value:,.0f}".replace(",", ".")

    @ui_operation()
    def get_profit_margin(self) -> str:
        total_sales = self.sale_service.get_total_sales(
            self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
        )
        total_profits = self.sale_service.get_total_profits(
            self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
        )
        if total_sales > 0:
            profit_margin = (total_profits / total_sales) * 100
            return f"{profit_margin:.2f}%"
    @ui_operation()
    def get_todays_sales(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        todays_sales = self.sale_service.get_total_sales(today, today)
        return f"${todays_sales:,.0f}".replace(",", ".")

    @ui_operation()
    def update_low_stock(self):
        try:
            low_stock_items = self.inventory_service.get_low_stock_products(threshold=10)
            self.low_stock_table.setRowCount(0)
            self.low_stock_table.setRowCount(len(low_stock_items))
            
            for row, item in enumerate(low_stock_items):
                self.low_stock_table.setItem(row, 0, NumericTableWidgetItem(item["id"]))
                self.low_stock_table.setItem(row, 1, QTableWidgetItem(item["name"]))
                self.low_stock_table.setItem(row, 2, NumericTableWidgetItem(item["quantity"]))
                
                # Highlight critical stock
                if item["quantity"] <= 3:
                     from ui.styles import DesignTokens
                     from PySide6.QtGui import QColor
                     for col in range(3):
                        item_widget = self.low_stock_table.item(row, col)
                        item_widget.setBackground(QColor(DesignTokens.COLOR_ERROR))
                        item_widget.setForeground(QColor("white"))

        except Exception as e:
            logger.error(f"Error updating low stock: {e}")

    @ui_operation()
    def create_profit_trend_chart(self):
        chart = QChart()
        chart.setTitle("Tendencia Ganancia Semanal (4 sem)")
        weekly_profit_trend = self.analytics_service.get_weekly_profit_trend(
            self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
        )

        # Handle the case of empty data
        if not weekly_profit_trend:
            chart.setTitle("Tendencia Ganancia Semanal (Sin Datos)")
            return QChartView(chart)

        series = QBarSeries()
        bar_set = QBarSet("Ganancia Semanal")
        weeks = []

        for data in weekly_profit_trend:
            bar_set.append(data["weekly_profit"])
            # Convert 'week_start' to a QDate for nice labeling

            week_start = QDate.fromString(data["week_start"], "yyyy-MM-dd")
            weeks.append(week_start.toString("MMM dd"))

        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(weeks)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setMin(0)

        # Safely do max() with fallback
        max_profit = max(d["weekly_profit"] for d in weekly_profit_trend)
        # Round up
        max_y = (ceil(max_profit / 10000) * 10000) + 10000
        axis_y.setMax(max_y)

        axis_y.setTickCount(6)
        axis_y.setLabelFormat("%d")

        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

        chart.setMargins(QMargins(10, 10, 10, 10))
        chart.layout().setContentsMargins(0, 0, 0, 0)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        return chart_view

    @ui_operation()
    def create_top_products_chart(self):
        chart = QChart()
        chart.setTitle("Top 5 Productos Rentables")
        top_products = self.analytics_service.get_profit_by_product(
            self.start_date.strftime("%Y-%m-%d"),
            self.end_date.strftime("%Y-%m-%d"),
            limit=5,
        )

        # Handle the case of empty data
        if not top_products:
            chart.setTitle("Top 5 Productos Rentables (Sin Datos)")
            return QChartView(chart)

        series = QBarSeries()
        bar_set = QBarSet("Ganancia")
        categories = []

        for product in top_products:
            bar_set.append(product["total_profit"])
            categories.append(product["name"])

        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setMin(0)

        # Safely do max() with fallback
        max_profit = max(prod["total_profit"] for prod in top_products)
        max_y = (ceil(max_profit / 5000) * 5000) + 5000
        axis_y.setMax(max_y)

        axis_y.setTickCount(6)
        axis_y.setLabelFormat("%d")

        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

        chart.setMargins(QMargins(10, 10, 10, 10))
        chart.layout().setContentsMargins(0, 0, 0, 0)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        return chart_view
