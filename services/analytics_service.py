from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from database import DatabaseManager
from config import LOYALTY_THRESHOLD
from functools import lru_cache
from utils.logger import logger

class AnalyticsService:
    @staticmethod
    @lru_cache(maxsize=32)
    def get_loyal_customers(threshold: int = LOYALTY_THRESHOLD) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT c.id, c.identifier_9, COUNT(DISTINCT s.id) as purchase_count
                FROM customers c
                JOIN sales s ON c.id = s.customer_id
                GROUP BY c.id
                HAVING purchase_count >= ?
                ORDER BY purchase_count DESC
            '''
            return DatabaseManager.fetch_all(query, (threshold,))
        except Exception as e:
            logger.error(f"Error getting loyal customers: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=32)
    def get_sales_by_weekday(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        try:
            query = '''
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
                    SUM(total_amount) as total_sales
                FROM sales
                WHERE date BETWEEN ? AND ?
                GROUP BY weekday
                ORDER BY CAST(strftime('%w', date) AS INTEGER)
            '''
            return DatabaseManager.fetch_all(query, (start_date, end_date))
        except Exception as e:
            logger.error(f"Error getting sales by weekday: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=32)
    def get_top_selling_products(start_date: str, end_date: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT p.id, p.name, SUM(si.quantity) as total_quantity, SUM(si.quantity * si.price) as total_revenue
                FROM products p
                JOIN sale_items si ON p.id = si.product_id
                JOIN sales s ON si.sale_id = s.id
                WHERE s.date BETWEEN ? AND ?
                GROUP BY p.id
                ORDER BY total_quantity DESC
                LIMIT ?
            '''
            return DatabaseManager.fetch_all(query, (start_date, end_date, limit))
        except Exception as e:
            logger.error(f"Error getting top selling products: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=32)
    def get_sales_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT date, SUM(total_amount) as daily_sales
                FROM sales
                WHERE date BETWEEN ? AND ?
                GROUP BY date
                ORDER BY date
            '''
            return DatabaseManager.fetch_all(query, (start_date, end_date))
        except Exception as e:
            logger.error(f"Error getting sales trend: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=32)
    def get_inventory_turnover(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT 
                    p.id, 
                    p.name, 
                    COALESCE(SUM(si.quantity), 0) as sold_quantity,
                    AVG(i.quantity) as avg_inventory,
                    CASE 
                        WHEN AVG(i.quantity) > 0 
                        THEN CAST(COALESCE(SUM(si.quantity), 0) AS FLOAT) / AVG(i.quantity)
                        ELSE 0 
                    END as turnover_ratio
                FROM products p
                LEFT JOIN sale_items si ON p.id = si.product_id
                LEFT JOIN sales s ON si.sale_id = s.id AND s.date BETWEEN ? AND ?
                LEFT JOIN inventory i ON p.id = i.product_id
                GROUP BY p.id
                ORDER BY turnover_ratio DESC
            '''
            return DatabaseManager.fetch_all(query, (start_date, end_date))
        except Exception as e:
            logger.error(f"Error getting inventory turnover: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=32)
    def get_category_performance(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT 
                    c.name as category,
                    SUM(si.quantity * si.price) as total_sales,
                    SUM(si.quantity) as number_of_products_sold
                FROM categories c
                JOIN products p ON c.id = p.category_id
                JOIN sale_items si ON p.id = si.product_id
                JOIN sales s ON si.sale_id = s.id
                WHERE s.date BETWEEN ? AND ?
                GROUP BY c.id
                ORDER BY total_sales DESC
            '''
            return DatabaseManager.fetch_all(query, (start_date, end_date))
        except Exception as e:
            logger.error(f"Error getting category performance: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=32)
    def get_profit_margin(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT 
                    p.id, 
                    p.name, 
                    SUM(si.quantity * si.price) as revenue,
                    SUM(si.quantity * p.cost_price) as cost,
                    (SUM(si.quantity * si.price) - SUM(si.quantity * p.cost_price)) as profit,
                    CASE 
                        WHEN SUM(si.quantity * si.price) > 0 
                        THEN ((SUM(si.quantity * si.price) - SUM(si.quantity * p.cost_price)) / SUM(si.quantity * si.price)) * 100
                        ELSE 0 
                    END as profit_margin
                FROM products p
                LEFT JOIN sale_items si ON p.id = si.product_id
                LEFT JOIN sales s ON si.sale_id = s.id
                WHERE s.date BETWEEN ? AND ?
                GROUP BY p.id
                ORDER BY profit_margin DESC
            '''
            return DatabaseManager.fetch_all(query, (start_date, end_date))
        except Exception as e:
            logger.error(f"Error getting profit margin: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=32)
    def get_customer_retention_rate(start_date: str, end_date: str) -> Dict[str, Any]:
        try:
            query = '''
                WITH customers_in_period AS (
                    SELECT DISTINCT customer_id
                    FROM sales
                    WHERE date BETWEEN ? AND ?
                ),
                returning_customers AS (
                    SELECT customer_id
                    FROM sales
                    WHERE date < ?
                    INTERSECT
                    SELECT customer_id
                    FROM sales
                    WHERE date BETWEEN ? AND ?
                )
                SELECT 
                    COUNT(DISTINCT c.customer_id) as total_customers,
                    COUNT(DISTINCT rc.customer_id) as returning_customers,
                    CASE 
                        WHEN COUNT(DISTINCT c.customer_id) > 0 
                        THEN CAST(COUNT(DISTINCT rc.customer_id) AS FLOAT) / COUNT(DISTINCT c.customer_id) * 100
                        ELSE 0 
                    END as retention_rate
                FROM customers_in_period c
                LEFT JOIN returning_customers rc ON c.customer_id = rc.customer_id
            '''
            result = DatabaseManager.fetch_one(query, (start_date, end_date, start_date, start_date, end_date))
            
            if result is None:
                # Return default values if no data is found
                return {
                    'total_customers': 0,
                    'returning_customers': 0,
                    'retention_rate': 0.0
                }
            
            return {
                'total_customers': result['total_customers'],
                'returning_customers': result['returning_customers'],
                'retention_rate': result['retention_rate']
            }
        except Exception as e:
            logger.error(f"Error getting customer retention rate: {str(e)}")
            raise

    @staticmethod
    def clear_cache():
        AnalyticsService.get_loyal_customers.cache_clear()
        AnalyticsService.get_sales_by_weekday.cache_clear()
        AnalyticsService.get_top_selling_products.cache_clear()
        AnalyticsService.get_sales_trend.cache_clear()
        AnalyticsService.get_inventory_turnover.cache_clear()
        AnalyticsService.get_category_performance.cache_clear()
        AnalyticsService.get_profit_margin.cache_clear()
        AnalyticsService.get_customer_retention_rate.cache_clear()