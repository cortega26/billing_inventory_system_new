from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from services.sale_service import SaleService
from services.purchase_service import PurchaseService
from services.inventory_service import InventoryService
from services.customer_service import CustomerService
from datetime import datetime, timedelta

class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self.sale_service = SaleService()
        self.purchase_service = PurchaseService()
        self.inventory_service = InventoryService()
        self.customer_service = CustomerService()
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=30)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top row with key metrics
        metrics_layout = QHBoxLayout()
        metrics_layout.addWidget(self.create_metric_widget("Total Sales", self.get_total_sales()))
        metrics_layout.addWidget(self.create_metric_widget("Total Purchases", self.get_total_purchases()))
        metrics_layout.addWidget(self.create_metric_widget("Inventory Value", self.get_inventory_value()))
        metrics_layout.addWidget(self.create_metric_widget("Total Customers", self.get_total_customers()))
        layout.addLayout(metrics_layout)

        # Charts row
        charts_layout = QHBoxLayout()
        charts_layout.addWidget(self.create_sales_by_category_chart())
        charts_layout.addWidget(self.create_top_customers_chart())
        layout.addLayout(charts_layout)

    def create_metric_widget(self, label, value):
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.Box)
        widget.setStyleSheet("QFrame { border: 1px solid #cccccc; border-radius: 5px; }")
        
        layout = QVBoxLayout(widget)
        label_widget = QLabel(label)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_widget = QLabel(str(value))
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        
        return widget

    def get_total_sales(self):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return f"${self.sale_service.get_total_sales(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')):,.2f}"

    def get_total_purchases(self):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        purchases = self.purchase_service.get_purchase_stats(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        return f"${purchases['total_amount']:,.2f}"

    def get_inventory_value(self):
        return f"${self.inventory_service.get_inventory_value():,.2f}"

    def get_total_customers(self):
        return len(self.customer_service.get_all_customers())

    def create_sales_by_category_chart(self):
        chart = QChart()
        chart.setTitle("Sales by Category (Last 30 Days)")
        
        series = QPieSeries()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        top_products = self.sale_service.get_top_selling_products(
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d'), 
            limit=5
        )
        
        for product in top_products:
            series.append(product['name'], product['total_revenue'])
        
        chart.addSeries(series)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        return chart_view

    def create_top_customers_chart(self):
        chart = QChart()
        chart.setTitle("Top 5 Customers")
        
        series = QBarSeries()
        bar_set = QBarSet("Purchase Amount")
        
        customers = self.customer_service.get_all_customers()
        customer_totals = [(customer, self.sale_service.get_total_sales_by_customer(customer.id)) for customer in customers]
        top_customers = sorted(customer_totals, key=lambda x: x[1], reverse=True)[:5]
        
        categories = []
        for customer, total in top_customers:
            bar_set.append(total)
            categories.append(customer.identifier_9)
        
        series.append(bar_set)
        chart.addSeries(series)
        
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        return chart_view