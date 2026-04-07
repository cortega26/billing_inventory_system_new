from typing import Dict, Type

from services.analytics.contracts import Metric
from utils.validation.validators import (
    validate_date,
    validate_float_non_negative,
    validate_integer,
)


class SalesDailyMetric(Metric):
    @property
    def name(self) -> str:
        return "sales_daily"

    @property
    def description(self) -> str:
        return "Daily sales aggregation (revenue and count) for a given date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {"date": str, "total_sales": int, "sale_count": int}

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT
                strftime('%Y-%m-%d', date) as date,
                SUM(total_amount) as total_sales,
                COUNT(*) as sale_count
            FROM sales
            WHERE date(date) BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m-%d', date)
            ORDER BY date ASC
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])


class WeekdaySalesMetric(Metric):
    @property
    def name(self) -> str:
        return "sales_weekday"

    @property
    def description(self) -> str:
        return "Sales aggregation grouped by weekday for a given date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {"weekday": str, "total_sales": int, "sale_count": int}

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT
                CASE CAST(strftime('%w', date) AS INTEGER)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    WHEN 6 THEN 'Saturday'
                END AS weekday,
                SUM(total_amount) as total_sales,
                COUNT(*) as sale_count
            FROM sales
            WHERE date(date) BETWEEN ? AND ?
            GROUP BY CAST(strftime('%w', date) AS INTEGER)
            ORDER BY CAST(strftime('%w', date) AS INTEGER)
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])


class TopProductsMetric(Metric):
    @property
    def name(self) -> str:
        return "top_products"

    @property
    def description(self) -> str:
        return "Top selling products by quantity sold within a date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "product_id": int,
            "name": str,
            "total_quantity": float,
            "total_revenue": int,
            "sale_count": int,
        }

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))
        validate_integer(kwargs.get("limit", 10), min_value=1)

    def get_query(self, **kwargs) -> str:
        return """
            SELECT 
                p.id as product_id, 
                p.name, 
                ROUND(SUM(si.quantity), 3) as total_quantity,
                CAST(SUM(ROUND(si.quantity * si.price)) AS INTEGER) as total_revenue,
                COUNT(DISTINCT s.id) as sale_count
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE date(s.date) BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY total_quantity DESC
            LIMIT ?
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"], kwargs.get("limit", 10))


class LowStockMetric(Metric):
    @property
    def name(self) -> str:
        return "low_stock"

    @property
    def description(self) -> str:
        return "Products with inventory quantity below a specified threshold."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {"product_id": int, "name": str, "quantity": float}

    def validate_params(self, **kwargs) -> None:
        validate_float_non_negative(kwargs.get("threshold", 10))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT 
                p.id as product_id, 
                p.name, 
                i.quantity
            FROM products p
            JOIN inventory i ON p.id = i.product_id
            WHERE i.quantity < ?
            ORDER BY i.quantity ASC
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs.get("threshold", 10),)


class InventoryAgingMetric(Metric):
    @property
    def name(self) -> str:
        return "inventory_aging"

    @property
    def description(self) -> str:
        return "Products with positive stock that haven't been sold in the last N days."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "product_id": int,
            "name": str,
            "stock_quantity": float,
            "last_sold_date": str,
        }

    def validate_params(self, **kwargs) -> None:
        validate_integer(kwargs.get("days", 30), min_value=0)

    def get_query(self, **kwargs) -> str:
        # We need products with quantity > 0
        # AND (no sales ever OR last sale was more than N days ago)
        return """
            SELECT 
                p.id as product_id,
                p.name,
                i.quantity as stock_quantity,
                MAX(s.date) as last_sold_date
            FROM products p
            JOIN inventory i ON p.id = i.product_id
            LEFT JOIN sale_items si ON p.id = si.product_id
            LEFT JOIN sales s ON si.sale_id = s.id
            WHERE i.quantity > 0
            GROUP BY p.id
            HAVING last_sold_date IS NULL 
               OR last_sold_date < date('now', '-' || ? || ' days')
            ORDER BY last_sold_date ASC
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (str(kwargs.get("days", 30)),)


class DepartmentSalesMetric(Metric):
    @property
    def name(self) -> str:
        return "department_sales"

    @property
    def description(self) -> str:
        return "Sales performance grouped by category (department) for a date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "category": str,
            "total_sales": int,
            "units_sold": float,
            "sale_count": int,
        }

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT 
                COALESCE(c.name, 'Uncategorized') as category,
                CAST(SUM(ROUND(si.quantity * si.price)) AS INTEGER) as total_sales,
                ROUND(SUM(si.quantity), 3) as units_sold,
                COUNT(DISTINCT s.id) as sale_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE date(s.date) BETWEEN ? AND ?
            GROUP BY c.id
            ORDER BY total_sales DESC
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])


class ProfitTrendMetric(Metric):
    @property
    def name(self) -> str:
        return "profit_trend"

    @property
    def description(self) -> str:
        return "Daily revenue and profit trend for a given date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "date": str,
            "daily_revenue": int,
            "daily_profit": int,
            "sale_count": int,
        }

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT
                strftime('%Y-%m-%d', date) as date,
                SUM(total_amount) as daily_revenue,
                SUM(total_profit) as daily_profit,
                COUNT(*) as sale_count
            FROM sales
            WHERE date(date) BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m-%d', date)
            ORDER BY strftime('%Y-%m-%d', date)
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])


class WeeklyProfitTrendMetric(Metric):
    @property
    def name(self) -> str:
        return "weekly_profit_trend"

    @property
    def description(self) -> str:
        return "Weekly profit trend with a representative week start date."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {"week": str, "week_start": str, "weekly_profit": int}

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT
                strftime('%Y-%W', date) as week,
                MIN(date(date)) as week_start,
                SUM(total_profit) as weekly_profit
            FROM sales
            WHERE date(date) BETWEEN ? AND ?
            GROUP BY week
            ORDER BY week
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])


class ProductProfitMetric(Metric):
    @property
    def name(self) -> str:
        return "product_profit"

    @property
    def description(self) -> str:
        return "Product profit analytics with revenue, cost, profit, volume, and sale count."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "product_id": int,
            "name": str,
            "total_revenue": int,
            "total_cost": int,
            "total_profit": int,
            "sales_volume": float,
            "sale_count": int,
        }

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))
        validate_integer(kwargs.get("limit", 10), min_value=1)

    def get_query(self, **kwargs) -> str:
        return """
            SELECT
                p.id as product_id,
                p.name,
                CAST(SUM(ROUND(si.quantity * si.price)) AS INTEGER) as total_revenue,
                CAST(SUM(ROUND(si.quantity * p.cost_price)) AS INTEGER) as total_cost,
                CAST(SUM(ROUND(si.quantity * (si.price - p.cost_price))) AS INTEGER) as total_profit,
                ROUND(SUM(si.quantity), 3) as sales_volume,
                COUNT(DISTINCT s.id) as sale_count
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE date(s.date) BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY total_profit DESC
            LIMIT ?
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"], kwargs.get("limit", 10))


class ProfitMarginDistributionMetric(Metric):
    @property
    def name(self) -> str:
        return "profit_margin_distribution"

    @property
    def description(self) -> str:
        return "Distribution of products by profit margin range for a date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "margin_range": str,
            "product_count": int,
            "average_margin": float,
            "total_sales": int,
        }

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT
                CASE
                    WHEN profit_margin < 0 THEN 'Loss'
                    WHEN profit_margin BETWEEN 0 AND 10 THEN '0-10%'
                    WHEN profit_margin BETWEEN 10 AND 20 THEN '10-20%'
                    WHEN profit_margin BETWEEN 20 AND 30 THEN '20-30%'
                    WHEN profit_margin BETWEEN 30 AND 40 THEN '30-40%'
                    ELSE '40%+'
                END as margin_range,
                COUNT(*) as product_count,
                ROUND(AVG(profit_margin), 2) as average_margin,
                SUM(total_sales) as total_sales
            FROM (
                SELECT
                    p.id,
                    CASE
                        WHEN CAST(SUM(ROUND(si.quantity * si.price)) AS INTEGER) > 0
                        THEN (
                            CAST(SUM(ROUND(si.quantity * (si.price - p.cost_price))) AS FLOAT) /
                            CAST(SUM(ROUND(si.quantity * si.price)) AS INTEGER)
                        ) * 100
                        ELSE 0
                    END as profit_margin,
                    CAST(SUM(ROUND(si.quantity * si.price)) AS INTEGER) as total_sales
                FROM products p
                JOIN sale_items si ON p.id = si.product_id
                JOIN sales s ON si.sale_id = s.id
                WHERE date(s.date) BETWEEN ? AND ?
                GROUP BY p.id
            ) as product_margins
            GROUP BY margin_range
            ORDER BY
                CASE margin_range
                    WHEN 'Loss' THEN 1
                    WHEN '0-10%' THEN 2
                    WHEN '10-20%' THEN 3
                    WHEN '20-30%' THEN 4
                    WHEN '30-40%' THEN 5
                    ELSE 6
                END
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])


class SalesSummaryMetric(Metric):
    @property
    def name(self) -> str:
        return "sales_summary"

    @property
    def description(self) -> str:
        return "Summary sales metrics for a date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "total_sales": int,
            "total_revenue": int,
            "total_profit": int,
            "average_sale_value": int,
            "unique_customers": int,
        }

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT
                COUNT(*) as total_sales,
                COALESCE(SUM(total_amount), 0) as total_revenue,
                COALESCE(SUM(total_profit), 0) as total_profit,
                COALESCE(ROUND(AVG(total_amount)), 0) as average_sale_value,
                COUNT(DISTINCT customer_id) as unique_customers
            FROM sales
            WHERE date(date) BETWEEN ? AND ?
        """

    def get_parameters(self, **kwargs) -> tuple:
        return (kwargs["start_date"], kwargs["end_date"])
