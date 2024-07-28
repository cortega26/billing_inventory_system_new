from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QTableWidget, QTableWidgetItem, QDateEdit)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QPainter
from PySide6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis, QLineSeries
from services.analytics_service import AnalyticsService
from utils.utils import create_table
from typing import List, Dict, Any

class AnalyticsView(QWidget):
    def __init__(self):
        super().__init__()
        self.analytics_service = AnalyticsService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Date range selection
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(QLabel("Start Date:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("End Date:"))
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # Buttons for different analytics
        button_layout = QHBoxLayout()
        loyal_customers_btn = QPushButton("Loyal Customers")
        loyal_customers_btn.clicked.connect(self.show_loyal_customers)
        sales_by_weekday_btn = QPushButton("Sales by Weekday")
        sales_by_weekday_btn.clicked.connect(self.show_sales_by_weekday)
        top_products_btn = QPushButton("Top Selling Products")
        top_products_btn.clicked.connect(self.show_top_selling_products)
        sales_trend_btn = QPushButton("Sales Trend")
        sales_trend_btn.clicked.connect(self.show_sales_trend)
        
        button_layout.addWidget(loyal_customers_btn)
        button_layout.addWidget(sales_by_weekday_btn)
        button_layout.addWidget(top_products_btn)
        button_layout.addWidget(sales_trend_btn)
        layout.addLayout(button_layout)

        # Table for displaying results
        self.result_table = create_table([])
        layout.addWidget(self.result_table)

        # Chart view
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.chart_view)

    def show_loyal_customers(self):
        loyal_customers = self.analytics_service.get_loyal_customers()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["ID", "9-digit Identifier", "4-digit Identifier", "Purchase Count"])
        self.result_table.setRowCount(len(loyal_customers))
        for row, customer in enumerate(loyal_customers):
            self.result_table.setItem(row, 0, QTableWidgetItem(str(customer['id'])))
            self.result_table.setItem(row, 1, QTableWidgetItem(customer['identifier_9']))
            self.result_table.setItem(row, 2, QTableWidgetItem(customer['identifier_4'] or "N/A"))
            self.result_table.setItem(row, 3, QTableWidgetItem(str(customer['purchase_count'])))

    def show_sales_by_weekday(self):
        sales_by_weekday = self.analytics_service.get_sales_by_weekday()
        self._populate_table_and_chart(sales_by_weekday, ["Weekday", "Total Sales"], 'weekday', 'total_sales', "Sales by Weekday")

    def show_top_selling_products(self):
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        top_products = self.analytics_service.get_top_selling_products(start_date, end_date)
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["Product ID", "Product Name", "Total Quantity"])
        self.result_table.setRowCount(len(top_products))
        for row, product in enumerate(top_products):
            self.result_table.setItem(row, 0, QTableWidgetItem(str(product['id'])))
            self.result_table.setItem(row, 1, QTableWidgetItem(product['name']))
            self.result_table.setItem(row, 2, QTableWidgetItem(str(product['total_quantity'])))

    def show_sales_trend(self):
        sales_trend = self.analytics_service.get_sales_trend()
        self._populate_table_and_chart(sales_trend, ["Date", "Daily Sales"], 'date', 'daily_sales', "Sales Trend", chart_type='line')

    def _populate_table_and_chart(self, data: List[Dict[str, Any]], headers: List[str], 
                                  x_key: str, y_key: str, title: str, chart_type: str = 'bar'):
        # Populate table
        self.result_table.setColumnCount(len(headers))
        self.result_table.setHorizontalHeaderLabels(headers)
        self.result_table.setRowCount(len(data))
        for row, item in enumerate(data):
            self.result_table.setItem(row, 0, QTableWidgetItem(str(item[x_key])))
            self.result_table.setItem(row, 1, QTableWidgetItem(f"{item[y_key]:,}"))  # Format as integer with thousands separator

        # Create chart
        chart = QChart()
        if chart_type == 'bar':
            series = QBarSeries()
            bar_set = QBarSet("")
            categories = []
            for item in data:
                bar_set.append(item[y_key])
                categories.append(str(item[x_key]))
            series.append(bar_set)
            chart.addSeries(series)
            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)
        elif chart_type == 'line':
            series = QLineSeries()
            for item in data:
                series.append(QDate.fromString(item[x_key], "yyyy-MM-dd").startOfDay().toMSecsSinceEpoch(), item[y_key])
            chart.addSeries(series)
            axis_x = QValueAxis()
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)

        axis_y = QValueAxis()
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        
        chart.setTitle(title)
        self.chart_view.setChart(chart)