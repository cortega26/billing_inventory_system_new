from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QDateEdit,
    QComboBox,
    QLineEdit,
    QFormLayout,
    QProgressBar,
    QHBoxLayout,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QPainter, QAction, QKeySequence
from PySide6.QtCharts import (
    QChart,
    QChartView,
    QBarSeries,
    QBarSet,
    QValueAxis,
    QBarCategoryAxis,
    QLineSeries,
    QDateTimeAxis,
    QPieSeries,
)
from services.analytics_service import AnalyticsService
from utils.helpers import (
    create_table,
    show_error_message,
    show_info_message,
    format_price,
)
from utils.ui.table_items import (
    NumericTableWidgetItem,
    PriceTableWidgetItem,
    PercentageTableWidgetItem,
)
from typing import List, Dict, Any
from utils.decorators import ui_operation


class AnalyticsView(QWidget):
    def __init__(self):
        super().__init__()
        self.analytics_service = AnalyticsService()
        self.setup_ui()
        self.setup_update_timer()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Date range selection
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(QLabel("Start Date:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("End Date:"))
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # Analytics type selection
        self.analytics_type = QComboBox()
        self.analytics_type.addItems(
            [
                "Loyal Customers",
                "Sales by Weekday",
                "Top Selling Products",
                "Sales Trend",
                "Category Performance",
                "Inventory Turnover",
                "Customer Retention Rate",
            ]
        )
        layout.addWidget(QLabel("Select Analysis:"))
        layout.addWidget(self.analytics_type)

        # Additional parameters
        self.params_layout = QFormLayout()
        self.top_n_spinbox = QSpinBox()
        self.top_n_spinbox.setRange(1, 100)
        self.top_n_spinbox.setValue(10)
        self.params_layout.addRow("Top N:", self.top_n_spinbox)
        layout.addLayout(self.params_layout)

        # Generate button
        generate_btn = QPushButton("Generate Analytics")
        generate_btn.clicked.connect(self.generate_analytics)
        layout.addWidget(generate_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Table for displaying results
        self.result_table = create_table([])
        layout.addWidget(self.result_table)

        # Chart view
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.chart_view)

        # Summary text
        self.summary_text = QLineEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text)

        # Set up shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.generate_analytics)
        self.addAction(refresh_shortcut)

    def setup_update_timer(self):
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_analytics)
        self.update_timer.start(300000)  # Update every 5 minutes

    @ui_operation(show_dialog=True)
    def generate_analytics(self):
        self.progress_bar.setValue(0)
        analytics_type = self.analytics_type.currentText()
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        top_n = self.top_n_spinbox.value()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            analytics_functions = {
                "Loyal Customers": self.show_loyal_customers,
                "Sales by Weekday": lambda: self.show_sales_by_weekday(
                    start_date, end_date
                ),
                "Top Selling Products": lambda: self.show_top_selling_products(
                    start_date, end_date, top_n
                ),
                "Sales Trend": lambda: self.show_sales_trend(start_date, end_date),
                "Category Performance": lambda: self.show_category_performance(
                    start_date, end_date
                ),
                "Inventory Turnover": lambda: self.show_inventory_turnover(
                    start_date, end_date
                ),
                "Customer Retention Rate": lambda: self.show_customer_retention_rate(
                    start_date, end_date
                ),
            }

            if analytics_type in analytics_functions:
                QTimer.singleShot(0, analytics_functions[analytics_type])
            else:
                show_error_message("Error", f"Unknown analytics type: {analytics_type}")
        finally:
            QApplication.restoreOverrideCursor()

        self.progress_bar.setValue(100)

    def update_analytics(self):
        self.generate_analytics()

    @ui_operation(show_dialog=True)
    def show_loyal_customers(self):
        loyal_customers = self.analytics_service.get_loyal_customers()
        self._populate_table_and_chart(
            loyal_customers,
            ["ID", "9-digit Identifier", "Purchase Count"],
            "identifier_9",
            "purchase_count",
            "Loyal Customers",
        )
        total_loyal = len(loyal_customers)
        avg_purchases = (
            sum(c["purchase_count"] for c in loyal_customers) / total_loyal
            if total_loyal > 0
            else 0
        )
        self.summary_text.setText(
            f"Total loyal customers: {total_loyal}, Average purchases: {format_price(avg_purchases)}"
        )

    @ui_operation(show_dialog=True)
    def show_sales_by_weekday(self, start_date: str, end_date: str):
        sales_by_weekday = self.analytics_service.get_sales_by_weekday(
            start_date, end_date
        )
        self._populate_table_and_chart(
            sales_by_weekday,
            ["Weekday", "Total Sales"],
            "weekday",
            "total_sales",
            "Sales by Weekday",
        )
        total_sales = sum(day["total_sales"] for day in sales_by_weekday)
        avg_daily_sales = total_sales / 7 if len(sales_by_weekday) == 7 else 0
        self.summary_text.setText(
            f"Total sales: {format_price(total_sales)}, Average daily sales: {format_price(avg_daily_sales)}"
        )

    @ui_operation(show_dialog=True)
    def show_top_selling_products(self, start_date: str, end_date: str, top_n: int):
        top_products = self.analytics_service.get_top_selling_products(
            start_date, end_date, top_n
        )
        self._populate_table_and_chart(
            top_products,
            ["Product ID", "Product Name", "Total Quantity", "Total Revenue"],
            "name",
            "total_quantity",
            "Top Selling Products",
        )
        total_quantity = sum(p["total_quantity"] for p in top_products)
        total_revenue = sum(p["total_revenue"] for p in top_products)
        self.summary_text.setText(
            f"Total quantity sold: {total_quantity}, Total revenue: ${total_revenue:.2f}"
        )

    @ui_operation(show_dialog=True)
    def show_sales_trend(self, start_date: str, end_date: str):
        sales_trend = self.analytics_service.get_sales_trend(start_date, end_date)
        self._populate_table_and_chart(
            sales_trend,
            ["Date", "Daily Sales"],
            "date",
            "daily_sales",
            "Sales Trend",
            chart_type="bar",
        )
        total_sales = sum(day["daily_sales"] for day in sales_trend)
        avg_daily_sales = total_sales / len(sales_trend) if sales_trend else 0
        self.summary_text.setText(
            f"Total sales: ${total_sales:.2f}, Average daily sales: ${avg_daily_sales:.2f}"
        )

    @ui_operation(show_dialog=True)
    def show_category_performance(self, start_date: str, end_date: str):
        category_performance = self.analytics_service.get_category_performance(
            start_date, end_date
        )
        self._populate_table_and_chart(
            category_performance,
            ["Category", "Total Sales", "Number of Products Sold"],
            "category",
            "total_sales",
            "Category Performance",
        )
        total_sales = sum(c["total_sales"] for c in category_performance)
        total_products_sold = sum(
            c["number_of_products_sold"] for c in category_performance
        )
        self.summary_text.setText(
            f"Total sales: ${total_sales:.2f}, Total products sold: {total_products_sold}"
        )

    @ui_operation(show_dialog=True)
    def show_inventory_turnover(self, start_date: str, end_date: str):
        inventory_turnover = self.analytics_service.get_inventory_turnover(
            start_date, end_date
        )
        self._populate_table_and_chart(
            inventory_turnover,
            ["Product ID", "Product Name", "Turnover Ratio"],
            "name",
            "turnover_ratio",
            "Inventory Turnover",
        )
        avg_turnover = (
            sum(p["turnover_ratio"] for p in inventory_turnover)
            / len(inventory_turnover)
            if inventory_turnover
            else 0
        )
        self.summary_text.setText(f"Average turnover ratio: {avg_turnover:.2f}")

    @ui_operation(show_dialog=True)
    def show_customer_retention_rate(self, start_date: str, end_date: str):
        retention_data = self.analytics_service.get_customer_retention_rate(
            start_date, end_date
        )
        self._populate_table_and_chart(
            [retention_data],
            ["Total Customers", "Returning Customers", "Retention Rate"],
            "retention_rate",
            "retention_rate",
            "Customer Retention Rate",
            chart_type="pie",
        )
        self.summary_text.setText(
            f"Customer retention rate: {retention_data['retention_rate']:.2f}%"
        )

    def _populate_table_and_chart(
        self,
        data: List[Dict[str, Any]],
        headers: List[str],
        x_key: str,
        y_key: str,
        title: str,
        chart_type: str = "bar",
    ):
        # Populate table
        self.result_table.setColumnCount(len(headers))
        self.result_table.setHorizontalHeaderLabels(headers)
        self.result_table.setRowCount(len(data))
        for row, item in enumerate(data):
            for col, header in enumerate(headers):
                key = header.lower().replace(" ", "_")
                value = item.get(key, "")
                if isinstance(value, (int, float)):
                    if header.lower().endswith("price") or header.lower().endswith(
                        "amount"
                    ):
                        self.result_table.setItem(
                            row, col, PriceTableWidgetItem(value, format_price)
                        )
                    elif header.lower().endswith(
                        "percentage"
                    ) or header.lower().endswith("rate"):
                        self.result_table.setItem(
                            row, col, PercentageTableWidgetItem(value)
                        )
                    else:
                        self.result_table.setItem(
                            row, col, NumericTableWidgetItem(value)
                        )
                else:
                    self.result_table.setItem(row, col, QTableWidgetItem(str(value)))

        # Create chart
        chart = QChart()
        if chart_type == "bar":
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
        elif chart_type == "line":
            series = QLineSeries()
            for item in data:
                date = QDate.fromString(item[x_key], "yyyy-MM-dd")
                series.append(date.startOfDay().toMSecsSinceEpoch(), item[y_key])
            chart.addSeries(series)

            axis_x = QDateTimeAxis()
            axis_x.setFormat("MMM dd")
            axis_x.setTickCount(5)
            min_date = QDate.fromString(data[0][x_key], "yyyy-MM-dd")
            max_date = QDate.fromString(data[-1][x_key], "yyyy-MM-dd")
            axis_x.setRange(min_date.startOfDay(), max_date.startOfDay())
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)
        elif chart_type == "pie":
            series = QPieSeries()
            for item in data:
                series.append(f"{x_key}: {item[x_key]:.2f}%", item[y_key])
            chart.addSeries(series)

        axis_y = QValueAxis()
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        if chart_type != "pie":
            series.attachAxis(axis_y)

        chart.setTitle(title)
        self.chart_view.setChart(chart)

    def refresh(self):
        self.generate_analytics()

    def show_context_menu(self, position):
        menu = QMenu()
        refresh_action = menu.addAction("Refresh")
        export_action = menu.addAction("Export to CSV")

        action = menu.exec(self.result_table.mapToGlobal(position))
        if action == refresh_action:
            self.refresh()
        elif action == export_action:
            self.export_to_csv()

    def export_to_csv(self):
        # TODO: Implement CSV export functionality
        show_info_message("Export", "CSV export functionality not implemented yet.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
        else:
            super().keyPressEvent(event)
