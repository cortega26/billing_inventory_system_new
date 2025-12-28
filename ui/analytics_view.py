###############################################################################
# File: analytics_view.py
# Purpose: Correctly handle multi-column bar charts (e.g., for "Profit by Product").
###############################################################################

from typing import Any, Dict, List, Optional

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QDateTimeAxis,
    QLineSeries,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.analytics_service import AnalyticsService
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import DatabaseException, UIException, ValidationException
from utils.helpers import create_table, format_price
from utils.system.logger import logger
from utils.ui.table_items import (
    NumericTableWidgetItem,
    PercentageTableWidgetItem,
    PriceTableWidgetItem,
)
from utils.validation.validators import validate_date, validate_integer


class AnalyticsView(QWidget):
    def __init__(self):
        super().__init__()
        self.analytics_service = AnalyticsService()
        self.setup_ui()
        self.setup_update_timer()

    @handle_exceptions(UIException, show_dialog=True)
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
        date_layout.addWidget(QLabel("Fecha Inicio:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("Fecha Fin:"))
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # Analytics type selection
        self.analytics_type = QComboBox()
        self.analytics_type.addItems(
            [
                "Ventas por Día de la Semana",
                "Productos Más Vendidos",
                "Tendencia de Ventas",
                "Rendimiento por Categoría",
                "Ganancia por Producto",
                "Tendencia de Ganancias",
                "Distribución Margen Ganancia",
            ]
        )
        layout.addWidget(QLabel("Seleccionar Análisis:"))
        layout.addWidget(self.analytics_type)

        # Additional parameters
        self.params_layout = QFormLayout()
        self.top_n_spinbox = QSpinBox()
        self.top_n_spinbox.setRange(1, 100)
        self.top_n_spinbox.setValue(10)
        self.params_layout.addRow("Top N:", self.top_n_spinbox)
        layout.addLayout(self.params_layout)

        # Generate button
        generate_btn = QPushButton("Generar Analítica")
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

        self.setLayout(layout)

    def setup_shortcuts(self):
        refresh_shortcut = QAction("Actualizar", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.generate_analytics)
        self.addAction(refresh_shortcut)

    def setup_update_timer(self):
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_analytics)
        self.update_timer.start(300000)  # Update every 5 minutes
        logger.info("Update timer setup completed.")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def generate_analytics(self):
        self.progress_bar.setValue(0)
        analytics_type = self.analytics_type.currentText()
        start_date = validate_date(self.start_date.date().toString("yyyy-MM-dd"))
        end_date = validate_date(self.end_date.date().toString("yyyy-MM-dd"))
        top_n = validate_integer(self.top_n_spinbox.value(), min_value=1, max_value=100)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            analytics_functions = {
                "Ventas por Día de la Semana": lambda: self.show_sales_by_weekday(
                    start_date, end_date
                ),
                "Productos Más Vendidos": lambda: self.show_top_selling_products(
                    start_date, end_date, top_n
                ),
                "Tendencia de Ventas": lambda: self.show_sales_trend(start_date, end_date),
                "Rendimiento por Categoría": lambda: self.show_category_performance(
                    start_date, end_date
                ),
                "Ganancia por Producto": lambda: self.show_profit_by_product(
                    start_date, end_date, top_n
                ),
                "Tendencia de Ganancias": lambda: self.show_profit_trend(start_date, end_date),
                "Distribución Margen Ganancia": lambda: self.show_profit_margin_distribution(
                    start_date, end_date
                ),
            }

            if analytics_type in analytics_functions:
                QTimer.singleShot(0, analytics_functions[analytics_type])
            else:
                raise ValidationException(f"Unknown analytics type: {analytics_type}")
        except Exception as e:
            logger.error(f"Error generating analytics: {str(e)}")
            raise UIException(f"Failed to generate analytics: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

        self.progress_bar.setValue(100)

    def update_analytics(self):
        self.generate_analytics()

    ############################################################################
    # Analysis methods
    ############################################################################

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def show_sales_by_weekday(self, start_date: str, end_date: str):
        try:
            data = self.analytics_service.get_sales_by_weekday(start_date, end_date)
            self._populate_table_and_chart(
                data=data,
                headers=["Día", "Ventas Totales"],
                keys=["weekday", "total_sales"],
                x_key="weekday",
                y_key="total_sales",
                title="Ventas por Día de la Semana",
                chart_type="bar",
            )
            total_sales = sum(day["total_sales"] for day in data)
            avg_daily_sales = total_sales / 7 if len(data) == 7 else 0
            self.summary_text.setText(
                f"Ventas totales: {format_price(total_sales)}, Promedio diario: {format_price(avg_daily_sales)}"
            )
            logger.info(f"Displayed sales by weekday analysis: {len(data)} days")
        except Exception as e:
            logger.error(f"Error showing sales by weekday: {str(e)}")
            raise DatabaseException(f"Failed to show sales by weekday: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def show_top_selling_products(self, start_date: str, end_date: str, top_n: int):
        try:
            data = self.analytics_service.get_top_selling_products(
                start_date, end_date, top_n
            )
            self._populate_table_and_chart(
                data=data,
                headers=[
                    "ID Producto",
                    "Producto",
                    "Cantidad Total",
                    "Ingresos Totales",
                ],
                keys=["product_id", "name", "total_quantity", "total_revenue"],
                x_key="name",
                y_key="total_quantity",
                title="Productos Más Vendidos",
                chart_type="bar",
            )
            total_quantity = sum(p["total_quantity"] for p in data)
            total_revenue = sum(p["total_revenue"] for p in data)
            self.summary_text.setText(
                f"Cantidad total vendida: {total_quantity}, Ingresos totales: ${total_revenue:.0f}"
            )
            logger.info(
                f"Displayed top selling products analysis: {len(data)} products"
            )
        except Exception as e:
            logger.error(f"Error showing top selling products: {str(e)}")
            raise DatabaseException(f"Failed to show top selling products: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def show_sales_trend(self, start_date: str, end_date: str):
        try:
            data = self.analytics_service.get_sales_trend(start_date, end_date)
            self._populate_table_and_chart(
                data=data,
                headers=["Fecha", "Ventas Diarias"],
                keys=["date", "daily_sales"],
                x_key="date",
                y_key="daily_sales",
                title="Tendencia de Ventas",
                chart_type="line",
            )
            total_sales = sum(day["daily_sales"] for day in data)
            avg_daily_sales = total_sales / len(data) if data else 0
            self.summary_text.setText(
                f"Ventas totales: ${total_sales}, Promedio diario: ${avg_daily_sales:.0f}"
            )
            logger.info(f"Displayed sales trend analysis: {len(data)} days")
        except Exception as e:
            logger.error(f"Error showing sales trend: {str(e)}")
            raise DatabaseException(f"Failed to show sales trend: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def show_category_performance(self, start_date: str, end_date: str):
        try:
            data = self.analytics_service.get_category_performance(start_date, end_date)
            self._populate_table_and_chart(
                data=data,
                headers=["Categoría", "Ventas Totales", "Productos Vendidos"],
                keys=["category", "total_sales", "number_of_products_sold"],
                x_key="category",
                y_key="total_sales",  # Single measure for bar chart
                title="Rendimiento por Categoría",
                chart_type="bar",
            )
            total_sales = sum(c["total_sales"] for c in data)
            total_products_sold = sum(c["number_of_products_sold"] for c in data)
            self.summary_text.setText(
                f"Ventas totales: ${total_sales:.0f}, Productos vendidos: {total_products_sold}"
            )
            logger.info(
                f"Displayed category performance analysis: {len(data)} categories"
            )
        except Exception as e:
            logger.error(f"Error showing category performance: {str(e)}")
            raise DatabaseException(f"Failed to show category performance: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def show_profit_by_product(self, start_date: str, end_date: str, top_n: int):
        try:
            data = self.analytics_service.get_profit_by_product(
                start_date, end_date, top_n
            )
            self._populate_table_and_chart(
                data=data,
                headers=[
                    "ID Producto",
                    "Producto",
                    "Ingresos Totales",
                    "Costo Total",
                    "Ganancia Total",
                ],
                keys=[
                    "product_id",
                    "name",
                    "total_revenue",
                    "total_cost",
                    "total_profit",
                ],
                x_key="name",
                y_key=None,
                title="Ganancia por Producto",
                chart_type="bar",
                metrics=["total_revenue", "total_cost", "total_profit"],
            )
            total_revenue = sum(p["total_revenue"] for p in data)
            total_profit = sum(p["total_profit"] for p in data)
            self.summary_text.setText(
                f"Ingresos totales: ${total_revenue:.0f}, Ganancia total: ${total_profit:.0f}"
            )
            logger.info(f"Displayed profit by product analysis: {len(data)} products")
        except Exception as e:
            logger.error(f"Error showing profit by product: {str(e)}")
            raise DatabaseException(f"Failed to show profit by product: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def show_profit_trend(self, start_date: str, end_date: str):
        try:
            data = self.analytics_service.get_profit_trend(start_date, end_date)
            self._populate_table_and_chart(
                data=data,
                headers=["Fecha", "Ingresos Diarios", "Ganancia Diaria"],
                keys=["date", "daily_revenue", "daily_profit"],
                x_key="date",
                y_key="daily_profit",
                title="Tendencia de Ganancias",
                chart_type="line",
            )
            total_revenue = sum(day["daily_revenue"] for day in data)
            total_profit = sum(day["daily_profit"] for day in data)
            self.summary_text.setText(
                f"Ingresos totales: ${total_revenue:.0f}, Ganancia total: ${total_profit:.0f}"
            )
            logger.info(f"Displayed profit trend analysis: {len(data)} days")
        except Exception as e:
            logger.error(f"Error showing profit trend: {str(e)}")
            raise DatabaseException(f"Failed to show profit trend: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def show_profit_margin_distribution(self, start_date: str, end_date: str):
        try:
            data = self.analytics_service.get_profit_margin_distribution(
                start_date, end_date
            )
            self._populate_table_and_chart(
                data=data,
                headers=["Rango Margen", "Cantidad Productos", "Margen Promedio"],
                keys=["margin_range", "product_count", "average_margin"],
                x_key="margin_range",
                y_key="product_count",
                title="Distribución Margen Ganancia",
                chart_type="pie",
            )
            total_products = sum(d["product_count"] for d in data)
            weighted_avg_margin = (
                sum(d["product_count"] * d["average_margin"] for d in data)
                / total_products
                if total_products > 0
                else 0
            )
            self.summary_text.setText(
                f"Total productos: {total_products}, Margen promedio ponderado: {weighted_avg_margin:.2f}%"
            )
            logger.info(
                f"Displayed profit margin distribution analysis: {len(data)} ranges"
            )
        except Exception as e:
            logger.error(f"Error showing profit margin distribution: {str(e)}")
            raise DatabaseException(
                f"Failed to show profit margin distribution: {str(e)}"
            )

    ############################################################################
    # The updated _populate_table_and_chart to handle multi-column bars
    ############################################################################
    def _populate_table_and_chart(
        self,
        data: List[Dict[str, Any]],
        headers: List[str],
        keys: List[str],
        x_key: str,
        y_key: Optional[str],
        title: str,
        chart_type: str = "bar",
        metrics: Optional[List[str]] = None,
    ):
        """
        Populates the result_table using 'headers' (for visualization) and 'keys' (for data lookup).
        Then displays a chart in chart_view.

        Args:
            data: List of dictionaries containing the data.
            headers: List of strings for table column headers (localized).
            keys: List of strings for data dictionary keys corresponding to the headers.
            x_key: Key for the X-axis (category/date).
            y_key: Key for the Y-axis (value).
            title: Title of the chart.
            chart_type: Type of chart ('bar', 'line', 'pie').
            metrics: Optional list of keys for multi-column bar charts.
        """

        # 1) Populate the table
        self.result_table.setColumnCount(len(headers))
        self.result_table.setHorizontalHeaderLabels(headers)
        self.result_table.setRowCount(len(data))

        for row_idx, item in enumerate(data):
            for col_idx, key in enumerate(keys):
                value = item.get(key, "")
                
                # Determine type for formatting based on keys/headers context
                # To be robust, we look at the key name
                if isinstance(value, (int, float)):
                    lower_key = key.lower()
                    if any(
                        s in lower_key
                        for s in ["price", "revenue", "sales", "profit", "cost"]
                    ):
                        self.result_table.setItem(
                            row_idx, col_idx, PriceTableWidgetItem(value, format_price)
                        )
                    elif "margin" in lower_key and "range" not in lower_key:
                        self.result_table.setItem(
                            row_idx, col_idx, PercentageTableWidgetItem(value)
                        )
                    else:
                        self.result_table.setItem(
                            row_idx, col_idx, NumericTableWidgetItem(value)
                        )
                else:
                    self.result_table.setItem(
                        row_idx, col_idx, QTableWidgetItem(str(value))
                    )

        # 2) Create the chart
        chart = QChart()

        if chart_type == "bar":
            # If 'metrics' is specified, we do multiple QBarSets for each metric
            # else we do single barSet with y_key
            series = QBarSeries()
            categories = []

            if metrics and len(metrics) > 1:
                # MULTI-COLUMN BARS: one QBarSet per metric
                bar_sets = {}
                # Initialize QBarSet objects for each metric
                for metric in metrics:
                    bar_set = QBarSet(metric)
                    bar_sets[metric] = bar_set
                    series.append(bar_set)

                # Build data
                for item in data:
                    cat_label = str(item[x_key])
                    categories.append(cat_label)

                    for metric in metrics:
                        bar_sets[metric].append(item.get(metric, 0))

            else:
                # SINGLE-COLUMN BARS (old approach)
                bar_set = QBarSet("")
                for item in data:
                    if y_key is not None:
                        bar_set.append(item[y_key])
                    categories.append(str(item[x_key]))
                series.append(bar_set)

            chart.addSeries(series)
            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)

            # Make sure axis_y is a QValueAxis
            axis_y = QValueAxis()
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)

        elif chart_type == "line":
            # single dimension line chart
            series = QLineSeries()
            for item in data:
                date_obj = QDate.fromString(item[x_key], "yyyy-MM-dd")
                if y_key is not None:
                    series.append(
                        date_obj.startOfDay().toMSecsSinceEpoch(), item[y_key]
                    )
            chart.addSeries(series)

            axis_x = QDateTimeAxis()
            axis_x.setFormat("MMM dd")
            axis_x.setTickCount(5)

            if data:
                min_date = QDate.fromString(data[0][x_key], "yyyy-MM-dd")
                max_date = QDate.fromString(data[-1][x_key], "yyyy-MM-dd")
                axis_x.setRange(min_date.startOfDay(), max_date.startOfDay())

            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)

            axis_y = QValueAxis()
            y_values = []
            for item in data:
                val = float(item[y_key]) if y_key else 0
                y_values.append(val)

            if y_values:
                max_val = max(y_values)
                axis_y.setRange(0, max_val * 1.1)  # or just max_val
            axis_y.setLabelFormat("%.0f")
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)

        elif chart_type == "pie":
            # single dimension pie
            series = QPieSeries()
            for item in data:
                x_value = item.get(x_key, "")
                y_value = item.get(y_key) if y_key else 0
                slice_label = f"{str(x_value)}: {y_value}"
                series.append(slice_label, item[y_key] if y_key else 0)
            chart.addSeries(series)

        chart.setTitle(title)
        self.chart_view.setChart(chart)

    def refresh(self):
        self.generate_analytics()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
        else:
            super().keyPressEvent(event)
