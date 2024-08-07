from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.sale import Sale, SaleItem
from services.inventory_service import InventoryService
from utils.decorators import db_operation, validate_input
from utils.exceptions import ValidationException
from functools import lru_cache

class SaleService:
    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def create_sale(customer_id: int, date: str, items: List[Dict[str, Any]]) -> Optional[int]:
        SaleService._validate_sale_items(items)
        total_amount = sum(item['quantity'] * item['sell_price'] for item in items)
        
        sale_id = SaleService._insert_sale(customer_id, date, total_amount)
        
        if sale_id is None:
            raise ValidationException("Failed to create sale record")

        SaleService._insert_sale_items(sale_id, items)
        SaleService._update_inventory(items)
        
        SaleService.clear_cache()
        return sale_id

    @staticmethod
    @db_operation(show_dialog=True)
    def get_sale(sale_id: int) -> Optional[Sale]:
        query = 'SELECT * FROM sales WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (sale_id,))
        if row:
            sale = Sale.from_db_row(row)
            sale.items = SaleService.get_sale_items(sale_id)
            return sale
        return None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    def get_all_sales() -> List[Sale]:
        query = 'SELECT * FROM sales ORDER BY date DESC'
        rows = DatabaseManager.fetch_all(query)
        sales = [Sale.from_db_row(row) for row in rows]
        for sale in sales:
            sale.items = SaleService.get_sale_items(sale.id)
        return sales

    @staticmethod
    @db_operation(show_dialog=True)
    def get_sale_items(sale_id: int) -> List[SaleItem]:
        query = 'SELECT * FROM sale_items WHERE sale_id = ?'
        rows = DatabaseManager.fetch_all(query, (sale_id,))
        return [SaleItem.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    def delete_sale(sale_id: int) -> None:
        items = SaleService.get_sale_items(sale_id)
        
        SaleService._revert_inventory(items)
        
        DatabaseManager.execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))
        DatabaseManager.execute_query('DELETE FROM sales WHERE id = ?', (sale_id,))
        SaleService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def get_total_sales(start_date: str, end_date: str) -> float:
        query = '''
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ?
        '''
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        return float(result['total'] if result else 0)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_sales_by_customer(customer_id: int) -> List[Sale]:
        query = 'SELECT * FROM sales WHERE customer_id = ? ORDER BY date DESC'
        rows = DatabaseManager.fetch_all(query, (customer_id,))
        sales = [Sale.from_db_row(row) for row in rows]
        for sale in sales:
            sale.items = SaleService.get_sale_items(sale.id)
        return sales

    @staticmethod
    @db_operation(show_dialog=True)
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
    @db_operation(show_dialog=True)
    def get_daily_sales(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = '''
            SELECT date, SUM(total_amount) as daily_total
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        '''
        return DatabaseManager.fetch_all(query, (start_date, end_date))

    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def update_sale(sale_id: int, customer_id: int, date: str, items: List[Dict[str, Any]]) -> None:
        SaleService._validate_sale_items(items)
        old_items = SaleService.get_sale_items(sale_id)
        
        SaleService._revert_inventory(old_items)
        
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        SaleService._update_sale(sale_id, customer_id, date, total_amount)
        SaleService._update_sale_items(sale_id, items)
        SaleService._update_inventory(items)
        
        SaleService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def get_sales_stats(start_date: str, end_date: str) -> Dict[str, Any]:
        query = '''
        SELECT 
            COUNT(DISTINCT s.id) as total_sales,
            SUM(s.total_amount) as total_revenue,
            AVG(s.total_amount) as average_sale_amount,
            COUNT(DISTINCT s.customer_id) as unique_customers
        FROM sales s
        WHERE s.date BETWEEN ? AND ?
        '''
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        return {
            'total_sales': result['total_sales'] if result else 0,
            'total_revenue': float(result['total_revenue']) if result and result['total_revenue'] else 0.0,
            'average_sale_amount': float(result['average_sale_amount']) if result and result['average_sale_amount'] else 0.0,
            'unique_customers': result['unique_customers'] if result else 0
        }

    @staticmethod
    @db_operation(show_dialog=True)
    def get_total_sales_by_customer(customer_id: int) -> float:
        query = '''
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE customer_id = ?
        '''
        result = DatabaseManager.fetch_one(query, (customer_id,))
        return float(result['total'] if result else 0)

    @staticmethod
    def clear_cache():
        SaleService.get_all_sales.cache_clear()

    @staticmethod
    def _validate_sale_items(items: List[Dict[str, Any]]) -> None:
        if not items:
            raise ValidationException("Sale must have at least one item")
        for item in items:
            if item['quantity'] <= 0 or item['sell_price'] <= 0:
                raise ValidationException("Item quantity and sell price must be positive")

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_sale(customer_id: int, date: str, total_amount: float) -> Optional[int]:
        query = 'INSERT INTO sales (customer_id, date, total_amount) VALUES (?, ?, ?)'
        cursor = DatabaseManager.execute_query(query, (customer_id, date, total_amount))
        return cursor.lastrowid

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        for item in items:
            query = '''
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (sale_id, item['product_id'], item['quantity'], item['sell_price']))

    @staticmethod
    def _update_inventory(items: List[Dict[str, Any]]) -> None:
        for item in items:
            InventoryService.update_quantity(item['product_id'], -item['quantity'])

    @staticmethod
    def _revert_inventory(items: List[SaleItem]) -> None:
        for item in items:
            InventoryService.update_quantity(item.product_id, item.quantity)

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale(sale_id: int, customer_id: int, date: str, total_amount: float) -> None:
        query = 'UPDATE sales SET customer_id = ?, date = ?, total_amount = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (customer_id, date, total_amount, sale_id))

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        DatabaseManager.execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))
        SaleService._insert_sale_items(sale_id, items)
