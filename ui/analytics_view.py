from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QTableWidget, QTableWidgetItem, QDateEdit, QComboBox)
from PySide6.QtCore import Qt, QDate, QDateTime
from PySide6.QtGui import QPainter
from PySide6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis, QLineSeries, QDateTimeAxis
from services.analytics_service import AnalyticsService
from utils.utils import create_table
from typing import List, Dict, Any
import datetime

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

        # Analytics type selection
        self.analytics_type = QComboBox()
        self.analytics_type.addItems(["Loyal Customers", "Sales by Weekday", "Top Selling Products", "Sales Trend"])
        layout.addWidget(self.analytics_type)

        # Generate button
        generate_btn = QPushButton("Generate Analytics")
        generate_btn.clicked.connect(self.generate_analytics)
        layout.addWidget(generate_btn)

        # Table for displaying results
        self.result_table = create_table([])
        layout.addWidget(self.result_table)

        # Chart view
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.chart_view)

    def generate_analytics(self):
        analytics_type = self.analytics_type.currentText()
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")

        if analytics_type == "Loyal Customers":
            self.show_loyal_customers()
        elif analytics_type == "Sales by Weekday":
            self.show_sales_by_weekday()
        elif analytics_type == "Top Selling Products":
            self.show_top_selling_products(start_date, end_date)
        elif analytics_type == "Sales Trend":
            self.show_sales_trend(start_date, end_date)

    def show_loyal_customers(self):
        loyal_customers = self.analytics_service.get_loyal_customers()
        self._populate_table_and_chart(loyal_customers, 
                                       ["ID", "9-digit Identifier", "Purchase Count"], 
                                       'identifier_9', 'purchase_count', "Loyal Customers")

    def show_sales_by_weekday(self):
        sales_by_weekday = self.analytics_service.get_sales_by_weekday()
        self._populate_table_and_chart(sales_by_weekday, 
                                       ["Weekday", "Total Sales"], 
                                       'weekday', 'total_sales', "Sales by Weekday")

    def show_top_selling_products(self, start_date: str, end_date: str):
        top_products = self.analytics_service.get_top_selling_products(start_date, end_date)
        self._populate_table_and_chart(top_products, 
                                       ["Product ID", "Product Name", "Total Quantity"], 
                                       'name', 'total_quantity', "Top Selling Products")

    def show_sales_trend(self, start_date: str, end_date: str):
        sales_trend = self.analytics_service.get_sales_trend()
        self._populate_table_and_chart(sales_trend, 
                                       ["Date", "Daily Sales"], 
                                       'date', 'daily_sales', "Sales Trend", 
                                       chart_type='line')

    def _populate_table_and_chart(self, data: List[Dict[str, Any]], headers: List[str], 
                                  x_key: str, y_key: str, title: str, chart_type: str = 'bar'):
        # Populate table
        self.result_table.setColumnCount(len(headers))
        self.result_table.setHorizontalHeaderLabels(headers)
        self.result_table.setRowCount(len(data))
        for row, item in enumerate(data):
            for col, header in enumerate(headers):
                self.result_table.setItem(row, col, QTableWidgetItem(str(item.get(header.lower().replace(' ', '_'), ''))))

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
            min_date = QDateTime()
            max_date = QDateTime()
            for item in data:
                date = QDateTime.fromString(item[x_key], "yyyy-MM-dd")
                series.append(date.toMSecsSinceEpoch(), item[y_key])
                if min_date.isNull() or min_date.secsTo(date) < 0:
                    min_date = date
                if max_date.isNull() or max_date.secsTo(date) > 0:
                    max_date = date
            chart.addSeries(series)
            
            axis_x = QDateTimeAxis()
            axis_x.setFormat("MMM dd")
            axis_x.setTickCount(5)
            if not min_date.isNull() and not max_date.isNull():
                axis_x.setRange(min_date, max_date)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)

        axis_y = QValueAxis()
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        
        chart.setTitle(title)
        self.chart_view.setChart(chart)