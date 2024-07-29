from typing import List, Dict, Any
from datetime import datetime, timedelta
from database import DatabaseManager
from config import LOYALTY_THRESHOLD

class AnalyticsService:
    @staticmethod
    def get_loyal_customers() -> List[Dict[str, Any]]:
        query = '''
            SELECT c.id, c.identifier_9, COUNT(DISTINCT s.id) as purchase_count
            FROM customers c
            JOIN sales s ON c.id = s.customer_id
            GROUP BY c.id
            HAVING purchase_count >= ?
        '''
        return DatabaseManager.fetch_all(query, (LOYALTY_THRESHOLD,))

    @staticmethod
    def get_sales_by_weekday() -> List[Dict[str, Any]]:
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
            GROUP BY weekday
            ORDER BY CAST(strftime('%w', date) AS INTEGER)
        '''
        return DatabaseManager.fetch_all(query)

    @staticmethod
    def get_top_selling_products(start_date: str, end_date: str, limit: int = 10) -> List[Dict[str, Any]]:
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

    @staticmethod
    def get_sales_trend(days: int = 30) -> List[Dict[str, Any]]:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        query = '''
            SELECT date, SUM(total_amount) as daily_sales
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        '''
        return DatabaseManager.fetch_all(query, (start_date.isoformat(), end_date.isoformat()))

    @staticmethod
    def get_inventory_turnover(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = '''
            SELECT 
                p.id, 
                p.name, 
                SUM(si.quantity) as sold_quantity,
                AVG(i.quantity) as avg_inventory,
                CASE 
                    WHEN AVG(i.quantity) > 0 
                    THEN CAST(SUM(si.quantity) AS FLOAT) / AVG(i.quantity)
                    ELSE 0 
                END as turnover_ratio
            FROM products p
            LEFT JOIN sale_items si ON p.id = si.product_id
            LEFT JOIN sales s ON si.sale_id = s.id
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY turnover_ratio DESC
        '''
        return DatabaseManager.fetch_all(query, (start_date, end_date))

    @staticmethod
    def get_profit_margin(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = '''
            SELECT 
                p.id, 
                p.name, 
                SUM(si.quantity * si.price) as revenue,
                SUM(si.quantity * COALESCE(pi.price, 0)) as cost,
                (SUM(si.quantity * si.price) - SUM(si.quantity * COALESCE(pi.price, 0))) as profit,
                CASE 
                    WHEN SUM(si.quantity * si.price) > 0 
                    THEN ((SUM(si.quantity * si.price) - SUM(si.quantity * COALESCE(pi.price, 0))) / SUM(si.quantity * si.price)) * 100
                    ELSE 0 
                END as profit_margin
            FROM products p
            LEFT JOIN sale_items si ON p.id = si.product_id
            LEFT JOIN sales s ON si.sale_id = s.id
            LEFT JOIN purchase_items pi ON p.id = pi.product_id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY profit_margin DESC
        '''
        return DatabaseManager.fetch_all(query, (start_date, end_date))