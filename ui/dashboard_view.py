from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from services.sale_service import SaleService
from services.purchase_service import PurchaseService
from services.inventory_service import InventoryService
from services.customer_service import CustomerService
from datetime import datetime, timedelta
from utils.event_system import event_system
from utils.logger import logger
from typing import Callable, Union


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

    def update_value(self):
        try:
            value = self.value_func()
            self.value_widget.setText(str(value))
        except Exception as e:
            logger.error(f"Error updating metric value: {str(e)}")
            self.value_widget.setText("N/A")

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
        self.setup_update_timer()
        self.setup_event_connections()

    def setup_event_connections(self):
        event_system.sale_added.connect(self.update_dashboard)
        event_system.purchase_added.connect(self.update_dashboard)
        event_system.inventory_changed.connect(self.update_dashboard)

    def setup_ui(self):
        try:
            layout = QVBoxLayout(self)

            # Top row with key metrics
            metrics_layout = QHBoxLayout()
            metrics_layout.addWidget(MetricWidget("Total Sales", self.get_total_sales))
            metrics_layout.addWidget(MetricWidget("Total Purchases", self.get_total_purchases))
            metrics_layout.addWidget(MetricWidget("Inventory Value", self.get_inventory_value))
            metrics_layout.addWidget(MetricWidget("Total Customers", self.get_total_customers))
            layout.addLayout(metrics_layout)

            # Charts row
            self.charts_layout = QHBoxLayout()
            self.sales_chart_view = self.create_sales_by_category_chart()
            self.customers_chart_view = self.create_top_customers_chart()
            self.charts_layout.addWidget(self.sales_chart_view)
            self.charts_layout.addWidget(self.customers_chart_view)
            layout.addLayout(self.charts_layout)

            logger.info("Dashboard UI setup completed successfully")
        except Exception as e:
            logger.error(f"Error setting up dashboard UI: {str(e)}")
            raise

    def setup_update_timer(self):
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_dashboard)
        self.update_timer.start(300000)  # Update every 5 minutes

    def create_metric_widget(self, label, value_func):
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.Box)
        widget.setStyleSheet("QFrame { border: 1px solid #cccccc; border-radius: 5px; }")
        
        layout = QVBoxLayout(widget)
        label_widget = QLabel(label)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_widget = QLabel()
        self.value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(label_widget)
        layout.addWidget(self.value_widget)

        self.update_metric_value(value_func)
        
        return widget

    def update_metric_value(self, value_func):
        try:
            value = value_func()
            self.value_widget.setText(str(value))
        except Exception as e:
            logger.error(f"Error updating metric value: {str(e)}")
            self.value_widget.setText("N/A")

    def get_total_sales(self) -> str:
        try:
            return f"${self.sale_service.get_total_sales(self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d')):,.2f}"
        except Exception as e:
            logger.error(f"Error getting total sales: {str(e)}")
            return "N/A"

    def get_total_purchases(self) -> str:
        try:
            purchases = self.purchase_service.get_purchase_stats(self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d'))
            return f"${purchases['total_amount']:,.2f}"
        except Exception as e:
            logger.error(f"Error getting total purchases: {str(e)}")
            return "N/A"

    def get_inventory_value(self) -> str:
        try:
            return f"${self.inventory_service.get_inventory_value():,.2f}"
        except Exception as e:
            logger.error(f"Error getting inventory value: {str(e)}")
            return "N/A"

    def get_total_customers(self) -> str:
        try:
            return str(len(self.customer_service.get_all_customers()))
        except Exception as e:
            logger.error(f"Error getting total customers: {str(e)}")
            return "N/A"

    def create_sales_by_category_chart(self):
        chart = QChart()
        chart.setTitle("Sales by Category (Last 30 Days)")
        
        try:
            series = QPieSeries()
            
            top_products = self.sale_service.get_top_selling_products(
                self.start_date.strftime('%Y-%m-%d'), 
                self.end_date.strftime('%Y-%m-%d'), 
                limit=5
            )
            
            # Define a diverse color palette
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F06292', '#AED581', '#7986CB', '#FFD54F', '#4DB6AC']
            
            for i, product in enumerate(top_products):
                slice = series.append(product['name'], product['total_revenue'])
                slice.setBrush(QColor(colors[i % len(colors)]))  # Use modulo to cycle through colors if more than 10 categories
            
            chart.addSeries(series)
        except Exception as e:
            logger.error(f"Error creating sales by category chart: {str(e)}")
            chart.setTitle("Sales by Category (Data Unavailable)")
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        return chart_view

    def create_top_customers_chart(self):
        chart = QChart()
        chart.setTitle("Top 5 Customer Groups")
        
        try:
            series = QBarSeries()
            
            customers = self.customer_service.get_all_customers()
            customer_totals = [(customer, self.sale_service.get_total_sales_by_customer(customer.id)) for customer in customers]
            
            # Group by 3or4_digit_identifier
            grouped_totals = {}
            for customer, total in customer_totals:
                group_id = customer.identifier_3or4 or 'Unknown'  # Use 3or4_digit_identifier, or 'Unknown' if not set
                if group_id in grouped_totals:
                    grouped_totals[group_id] += total
                else:
                    grouped_totals[group_id] = total
            
            # Sort and get top 5 groups
            top_groups = sorted(grouped_totals.items(), key=lambda x: x[1], reverse=True)[:5]
            
            bar_set = QBarSet("Purchase Amount")
            categories = []
            for group_id, total in top_groups:
                bar_set.append(total)
                categories.append(group_id)
            
            series.append(bar_set)
            chart.addSeries(series)
            
            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)
            
            axis_y = QValueAxis()
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)
        except Exception as e:
            logger.error(f"Error creating top customer groups chart: {str(e)}")
            chart.setTitle("Top 5 Customer Groups (Data Unavailable)")
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        return chart_view

    def update_dashboard(self):
        try:
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
            new_sales_chart = self.create_sales_by_category_chart()
            new_customers_chart = self.create_top_customers_chart()
            
            self.charts_layout.replaceWidget(self.sales_chart_view, new_sales_chart)
            self.charts_layout.replaceWidget(self.customers_chart_view, new_customers_chart)
            
            self.sales_chart_view.deleteLater()
            self.customers_chart_view.deleteLater()
            
            self.sales_chart_view = new_sales_chart
            self.customers_chart_view = new_customers_chart
            
            logger.info("Dashboard updated successfully")
        except Exception as e:
            logger.error(f"Error updating dashboard: {str(e)}")
