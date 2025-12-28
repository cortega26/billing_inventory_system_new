from typing import Dict, List, Type, Any
from services.analytics.contracts import Metric
from utils.validation.validators import validate_date, validate_integer, validate_float_non_negative

class SalesDailyMetric(Metric):
    @property
    def name(self) -> str:
        return "sales_daily"

    @property
    def description(self) -> str:
        return "Daily sales aggregation (revenue and count) for a given date range."

    @property
    def output_schema(self) -> Dict[str, Type]:
        return {
            "date": str,
            "total_sales": int,
            "sale_count": int
        }

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
            "total_revenue": int
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
                SUM(si.quantity) as total_quantity, 
                SUM(si.quantity * si.price) as total_revenue
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
        return {
            "product_id": int,
            "name": str,
            "quantity": float
        }

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
            "last_sold_date": str
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
            "units_sold": float
        }

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs.get("start_date"))
        validate_date(kwargs.get("end_date"))

    def get_query(self, **kwargs) -> str:
        return """
            SELECT 
                COALESCE(c.name, 'Uncategorized') as category,
                SUM(si.quantity * si.price) as total_sales,
                SUM(si.quantity) as units_sold
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
