from typing import List, Dict, Any, Tuple
from database.database_manager import DatabaseManager
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
                   ROUND(SUM(si.quantity), 3) as total_quantity, 
                   SUM(ROUND(si.quantity * si.price)) as total_revenue,
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
        logger.info("Top selling products retrieved", extra={
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit
        })
        return result

    ###########################################################################
    # FIX 1: Summation & date truncation for daily-based "Sales Trend"
    ###########################################################################
    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Returns a list of { 'date': 'YYYY-MM-DD', 'daily_sales': sum_of_that_day, 'sale_count': ...}
        ensuring the line chart can parse date with "yyyy-MM-dd" and sums daily totals.
        """
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT
                strftime('%Y-%m-%d', date) as date,
                SUM(total_amount) as daily_sales,
                COUNT(*) as sale_count
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m-%d', date)
            ORDER BY strftime('%Y-%m-%d', date)
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
                SUM(ROUND(si.quantity * (si.price - p.cost_price))) as total_profit,
                ROUND(SUM(si.quantity), 3) as sales_volume
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
                SUM(ROUND(si.quantity * si.price)) as total_sales,
                ROUND(SUM(si.quantity), 3) as number_of_products_sold,
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
                   SUM(ROUND(si.quantity * si.price)) as total_revenue,
                   SUM(ROUND(si.quantity * p.cost_price)) as total_cost,
                   SUM(ROUND(si.quantity * (si.price - p.cost_price))) as total_profit,
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
            SELECT
                strftime('%Y-%m-%d', date) as date,
                SUM(total_amount) as daily_revenue,
                SUM(total_profit) as daily_profit,
                COUNT(*) as sale_count
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m-%d', date)
            ORDER BY strftime('%Y-%m-%d', date)
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
                ROUND(AVG(profit_margin), 2) as average_margin,
                SUM(total_sales) as total_sales
            FROM (
                SELECT 
                    p.id,
                    CASE 
                        WHEN SUM(ROUND(si.quantity * si.price)) > 0 
                        THEN (CAST(SUM(ROUND(si.quantity * (si.price - p.cost_price))) AS FLOAT) / 
                              SUM(ROUND(si.quantity * si.price))) * 100
                        ELSE 0 
                    END as profit_margin,
                    SUM(ROUND(si.quantity * si.price)) as total_sales
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
                COALESCE(ROUND(AVG(total_amount)), 0) as average_sale_value,
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
        return dict(result)

    @staticmethod
    def clear_cache():
        AnalyticsService.get_sales_by_weekday.cache_clear()
        AnalyticsService.get_top_selling_products.cache_clear()
        AnalyticsService.get_sales_trend.cache_clear()
        AnalyticsService.get_weekly_profit_trend.cache_clear()
        AnalyticsService.get_profit_and_volume_by_product.cache_clear()
        AnalyticsService.get_category_performance.cache_clear()
        AnalyticsService.get_profit_by_product.cache_clear()
        AnalyticsService.get_profit_trend.cache_clear()
        AnalyticsService.get_profit_margin_distribution.cache_clear()
        logger.debug("Analytics cache cleared")

    @staticmethod
    def get_date_range(range_type: str) -> Tuple[str, str]:
        today = datetime.now().date()
        date_ranges = {
            'today': (today, today),
            'yesterday': (today - timedelta(days=1), today - timedelta(days=1)),
            'this_week': (today - timedelta(days=today.weekday()), today),
            'this_month': (today.replace(day=1), today),
            'this_year': (today.replace(month=1, day=1), today)
        }

        if range_type in date_ranges:
            start_date, end_date = date_ranges[range_type]
            logger.debug(f"Date range for {range_type}: {start_date} to {end_date}")
            return start_date.isoformat(), end_date.isoformat()
        else:
            logger.error(f"Invalid range type: {range_type}")
            raise ValueError("Invalid range type")

    def _validate_date_range(self, start_date: str, end_date: str) -> None:
        """Validate date range for analytics queries."""
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            today = datetime.now()
            
            if start > today or end > today:
                raise ValidationException("Date range cannot be in the future")
            if start > end:
                raise ValidationException("Start date must be before end date")
                
        except ValueError as e:
            raise ValidationException(f"Invalid date format: {str(e)}")
