from typing import List, Dict, Any, Tuple
from database import DatabaseManager
from functools import lru_cache
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import ValidationException, DatabaseException
from utils.validation.validators import validate_integer, validate_date
from utils.system.logger import logger
from datetime import datetime, timedelta

class AnalyticsService:
    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_by_weekday(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
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
            WHERE date BETWEEN ? AND ?
            GROUP BY weekday
            ORDER BY CAST(strftime('%w', date) AS INTEGER)
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date))
        logger.info("Sales by weekday retrieved", extra={"start_date": start_date, "end_date": end_date})
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_top_selling_products(start_date: str, end_date: str, limit: int = 10) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        limit = validate_integer(limit, min_value=1)
        query = """
            SELECT p.id, p.name, 
                   SUM(si.quantity) as total_quantity, 
                   SUM(si.quantity * si.price) as total_revenue,
                   COUNT(DISTINCT s.id) as sale_count
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY total_quantity DESC
            LIMIT ?
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date, limit))
        logger.info("Top selling products retrieved", extra={"start_date": start_date, "end_date": end_date, "limit": limit})
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT date, 
                   CAST(ROUND(SUM(total_amount), 0) AS INTEGER) as daily_sales,
                   COUNT(*) as sale_count
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date))
        logger.info("Sales trend retrieved", extra={"start_date": start_date, "end_date": end_date})
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_weekly_profit_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT 
                strftime('%Y-%W', date) as week,
                MIN(date) as week_start,
                SUM(total_profit) as weekly_profit
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY week
            ORDER BY week
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date))
        logger.info("Weekly profit trend retrieved", extra={"start_date": start_date, "end_date": end_date})
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_and_volume_by_product(start_date: str, end_date: str, limit: int = 5) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        limit = validate_integer(limit, min_value=1, max_value=100)
        query = """
            SELECT 
                p.id,
                p.name,
                SUM(si.quantity * (si.price - p.cost_price)) as total_profit,
                SUM(si.quantity) as sales_volume
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY total_profit DESC
            LIMIT ?
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date, limit))
        logger.info(f"Retrieved profit and volume by product: {len(result)} products")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_category_performance(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT 
                c.name as category,
                SUM(si.quantity * si.price) as total_sales,
                SUM(si.quantity) as number_of_products_sold,
                COUNT(DISTINCT s.id) as sale_count
            FROM categories c
            JOIN products p ON c.id = p.category_id
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY c.id
            ORDER BY total_sales DESC
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date))
        logger.info("Category performance retrieved", extra={"start_date": start_date, "end_date": end_date})
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_by_product(start_date: str, end_date: str, limit: int = 10) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        limit = validate_integer(limit, min_value=1)
        query = """
            SELECT p.id, p.name, 
                   SUM(si.quantity * si.price) as total_revenue,
                   SUM(si.quantity * p.cost_price) as total_cost,
                   SUM(si.quantity * (si.price - p.cost_price)) as total_profit,
                   COUNT(DISTINCT s.id) as sale_count
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY total_profit DESC
            LIMIT ?
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date, limit))
        logger.info(f"Retrieved profit by product: {len(result)} products")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT date, 
                SUM(total_amount) as daily_revenue,
                SUM(total_profit) as daily_profit,
                COUNT(*) as sale_count
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date))
        logger.info(f"Retrieved profit trend: {len(result)} days")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_margin_distribution(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
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
                AVG(profit_margin) as average_margin,
                SUM(total_sales) as total_sales
            FROM (
                SELECT 
                    p.id,
                    CASE 
                        WHEN SUM(si.quantity * si.price) > 0 
                        THEN (SUM(si.quantity * (si.price - p.cost_price)) / SUM(si.quantity * si.price)) * 100
                        ELSE 0 
                    END as profit_margin,
                    SUM(si.quantity * si.price) as total_sales
                FROM products p
                JOIN sale_items si ON p.id = si.product_id
                JOIN sales s ON si.sale_id = s.id
                WHERE s.date BETWEEN ? AND ?
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
        result = DatabaseManager.fetch_all(query, (start_date, end_date))
        logger.info(f"Retrieved profit margin distribution: {len(result)} ranges")
        return result

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_summary(start_date: str, end_date: str) -> Dict[str, Any]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT 
                COUNT(*) as total_sales,
                COALESCE(SUM(total_amount), 0) as total_revenue,
                COALESCE(SUM(total_profit), 0) as total_profit,
                COALESCE(AVG(total_amount), 0) as average_sale_value,
                COUNT(DISTINCT customer_id) as unique_customers
            FROM sales
            WHERE date BETWEEN ? AND ?
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        if result is None:
            logger.warning(f"No sales data found for period {start_date} to {end_date}")
            return {
                "total_sales": 0,
                "total_revenue": 0,
                "total_profit": 0,
                "average_sale_value": 0,
                "unique_customers": 0
            }
        logger.info(f"Retrieved sales summary from {start_date} to {end_date}")
        return dict(result)  # Convert sqlite3.Row to dict

    @staticmethod
    def clear_cache():
        AnalyticsService.get_sales_by_weekday.cache_clear()
        AnalyticsService.get_top_selling_products.cache_clear()
        AnalyticsService.get_sales_trend.cache_clear()
        AnalyticsService.get_category_performance.cache_clear()
        AnalyticsService.get_profit_by_product.cache_clear()
        AnalyticsService.get_profit_trend.cache_clear()
        AnalyticsService.get_profit_margin_distribution.cache_clear()
        logger.debug("Analytics cache cleared")

    @staticmethod
    def get_date_range(range_type: str) -> Tuple[str, str]:
        today = datetime.now().date()
        if range_type == 'today':
            return today.isoformat(), today.isoformat()
        elif range_type == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday.isoformat(), yesterday.isoformat()
        elif range_type == 'this_week':
            start_of_week = today - timedelta(days=today.weekday())
            return start_of_week.isoformat(), today.isoformat()
        elif range_type == 'this_month':
            start_of_month = today.replace(day=1)
            return start_of_month.isoformat(), today.isoformat()
        elif range_type == 'this_year':
            start_of_year = today.replace(month=1, day=1)
            return start_of_year.isoformat(), today.isoformat()
        else:
            raise ValueError("Invalid range type")
