from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QDate, QMargins
from PySide6.QtGui import QPainter
from PySide6.QtCharts import (
    QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
)
from services.sale_service import SaleService
from services.purchase_service import PurchaseService
from services.inventory_service import InventoryService
from services.customer_service import CustomerService
from services.analytics_service import AnalyticsService
from datetime import datetime, timedelta
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.decorators import ui_operation
from typing import Callable, Union
from math import ceil

class MetricWidget(QFrame):
    def __init__(self, label: str, value_func: Callable[[], Union[str, int, float]]):
        super().__init__()
        self.value_func = value_func
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet("QFrame { border: 1px solid #cccccc; border-radius: 5px; }")

        layout = QVBoxLayout(self)
        self.label_widget = QLabel(label)
        self.label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_widget = QLabel()
        self.value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        self.start_date = self.end_date - timedelta(days=30)
        self.setup_ui()
        self.setup_update_timer()
        self.setup_event_connections()

    def setup_event_connections(self):
        event_system.sale_added.connect(self.update_dashboard)
        event_system.purchase_added.connect(self.update_dashboard)
        event_system.inventory_changed.connect(self.update_dashboard)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top row with key metrics
        metrics_layout = QHBoxLayout()
        metrics_layout.addWidget(MetricWidget("Total Sales", self.get_total_sales))
        metrics_layout.addWidget(MetricWidget("Total Profits", self.get_total_profits))
        metrics_layout.addWidget(MetricWidget("Inventory Value", self.get_inventory_value))
        metrics_layout.addWidget(MetricWidget("Profit Margin", self.get_profit_margin))
        layout.addLayout(metrics_layout)

        # Charts row
        self.charts_layout = QHBoxLayout()
        self.profit_trend_chart_view = self.create_profit_trend_chart()
        self.top_products_chart_view = self.create_top_products_chart()

        # Set fixed size policies for both charts
        self.profit_trend_chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.top_products_chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Add charts to the layout with a 1:1 ratio
        self.charts_layout.addWidget(self.profit_trend_chart_view, 1)
        self.charts_layout.addWidget(self.top_products_chart_view, 1)

        layout.addLayout(self.charts_layout)

    def setup_update_timer(self):
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_dashboard)
        self.update_timer.start(600000)  # Update every 10 minutes

    @ui_operation()
    def get_total_sales(self) -> str:
        return f"${self.sale_service.get_total_sales(self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d')):,.0f}".replace(',', '.')

    @ui_operation()
    def get_total_profits(self) -> str:
        return f"${self.sale_service.get_total_profits(self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d')):,.0f}".replace(',', '.')

    @ui_operation()
    def get_inventory_value(self) -> str:
        return f"${self.inventory_service.get_inventory_value():,.0f}".replace(',', '.')

    @ui_operation()
    def get_profit_margin(self) -> str:
        total_sales = self.sale_service.get_total_sales(self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d'))
        total_profits = self.sale_service.get_total_profits(self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d'))
        if total_sales > 0:
            profit_margin = (total_profits / total_sales) * 100
            return f"{profit_margin:.2f}%"
        return "0.00%"

    @ui_operation()
    def create_profit_trend_chart(self):
        chart = QChart()
        chart.setTitle("Weekly Profit Trend (Last 4 Weeks)")
        weekly_profit_trend = self.analytics_service.get_weekly_profit_trend(
            self.start_date.strftime("%Y-%m-%d"),
            self.end_date.strftime("%Y-%m-%d")
        )
        series = QBarSeries()
        bar_set = QBarSet("Weekly Profit")
        axis_x = QBarCategoryAxis()
        weeks = []
        for data in weekly_profit_trend:
            week_start = QDate.fromString(data['week_start'], "yyyy-MM-dd")
            bar_set.append(data['weekly_profit'])
            weeks.append(week_start.toString("MMM dd"))
        series.append(bar_set)
        chart.addSeries(series)

        axis_x.append(weeks)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setMin(0)  # Set the minimum value of Y-axis to 0
        max_profit = max(data['weekly_profit'] for data in weekly_profit_trend)
        
        # Round up the max value to the nearest 10000
        max_y = (ceil(max_profit / 10000) * 10000) + 10000
        
        axis_y.setMax(max_y)
        
        # Set the number of ticks to 6 (5 intervals)
        tick_count = 6
        axis_y.setTickCount(tick_count)
        
        # Set the label format to display whole numbers
        axis_y.setLabelFormat("%d")
        
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Standardize legend position
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

        # Adjust the chart margins
        chart.setMargins(QMargins(10, 10, 10, 10))
        chart.layout().setContentsMargins(0, 0, 0, 0)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        return chart_view

    @ui_operation()
    def create_top_products_chart(self):
        chart = QChart()
        chart.setTitle("Top 5 Profitable Products")
        top_products = self.analytics_service.get_profit_by_product(
            self.start_date.strftime("%Y-%m-%d"),
            self.end_date.strftime("%Y-%m-%d"),
            limit=5
        )
        series = QBarSeries()
        
        bar_set = QBarSet("Profit")
        categories = []
        for product in top_products:
            bar_set.append(product['total_profit'])
            categories.append(product['name'])
        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setMin(0)  # Set the minimum value of Y-axis to 0
        max_profit = max(product['total_profit'] for product in top_products)
        
        # Round up the max value to the nearest 5000
        max_y = (ceil(max_profit / 5000) * 5000) + 5000
        
        axis_y.setMax(max_y)
        
        # Set the number of ticks to 6 (5 intervals)
        tick_count = 6
        axis_y.setTickCount(tick_count)
        
        # Set the label format to display whole numbers
        axis_y.setLabelFormat("%d")
        
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Standardize legend position
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

        # Adjust the chart margins
        chart.setMargins(QMargins(10, 10, 10, 10))
        chart.layout().setContentsMargins(0, 0, 0, 0)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        return chart_view

    @ui_operation()
    def update_dashboard(self, *args):
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=30)

        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            if isinstance(item, QHBoxLayout):
                for j in range(item.count()):
                    widget = item.itemAt(j).widget()
                    if isinstance(widget, MetricWidget):
                        widget.update_value()

        # Update charts
        new_profit_trend_chart = self.create_profit_trend_chart()
        new_top_products_chart = self.create_top_products_chart()

        # Set fixed size policies for new charts
        new_profit_trend_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        new_top_products_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.charts_layout.replaceWidget(self.profit_trend_chart_view, new_profit_trend_chart)
        self.charts_layout.replaceWidget(self.top_products_chart_view, new_top_products_chart)

        self.profit_trend_chart_view.deleteLater()
        self.top_products_chart_view.deleteLater()

        self.profit_trend_chart_view = new_profit_trend_chart
        self.top_products_chart_view = new_top_products_chart

        logger.info("Dashboard updated successfully")

    def refresh(self):
        self.update_dashboard()
