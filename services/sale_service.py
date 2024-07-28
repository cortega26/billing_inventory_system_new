from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from database import DatabaseManager
from models.sale import Sale, SaleItem
from services.inventory_service import InventoryService

class SaleService:
    @staticmethod
    def create_sale(customer_id: int, date: str, items: List[Dict[str, Any]]) -> Optional[int]:
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        query = 'INSERT INTO sales (customer_id, date, total_amount) VALUES (?, ?, ?)'
        cursor = DatabaseManager.execute_query(query, (customer_id, date, total_amount))
        sale_id = cursor.lastrowid
        
        if sale_id is None:
            return None

        for item in items:
            query = '''
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (sale_id, item['product_id'], item['quantity'], item['price']))
            
            InventoryService.update_quantity(item['product_id'], -item['quantity'])
        
        return sale_id

    @staticmethod
    def get_sale(sale_id: int) -> Optional[Sale]:
        query = 'SELECT * FROM sales WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (sale_id,))
        return Sale.from_row(row) if row else None

    @staticmethod
    def get_all_sales() -> List[Sale]:
        query = 'SELECT * FROM sales'
        rows = DatabaseManager.fetch_all(query)
        return [Sale.from_row(row) for row in rows]

    @staticmethod
    def get_sale_items(sale_id: int) -> List[SaleItem]:
        query = 'SELECT * FROM sale_items WHERE sale_id = ?'
        rows = DatabaseManager.fetch_all(query, (sale_id,))
        return [SaleItem.from_row(row) for row in rows]

    @staticmethod
    def delete_sale(sale_id: int) -> None:
        items = SaleService.get_sale_items(sale_id)
        
        for item in items:
            InventoryService.update_quantity(item.product_id, item.quantity)
        
        DatabaseManager.execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))
        DatabaseManager.execute_query('DELETE FROM sales WHERE id = ?', (sale_id,))

    @staticmethod
    def get_total_sales(start_date: str, end_date: str) -> int:
        query = '''
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ?
        '''
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        return result['total'] if result else 0

    @staticmethod
    def get_sales_by_customer(customer_id: int) -> List[Sale]:
        query = 'SELECT * FROM sales WHERE customer_id = ?'
        rows = DatabaseManager.fetch_all(query, (customer_id,))
        return [Sale.from_row(row) for row in rows]

    @staticmethod
    def get_top_selling_products(limit: int = 10) -> List[Dict[str, Any]]:
        query = '''
            SELECT p.id, p.name, SUM(si.quantity) as total_quantity, SUM(si.quantity * si.price) as total_revenue
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            GROUP BY p.id
            ORDER BY total_quantity DESC
            LIMIT ?
        '''
        return DatabaseManager.fetch_all(query, (limit,))

    @staticmethod
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
    def update_sale(sale_id: int, updated_sale_data: Dict[str, Any]) -> None:
        original_sale = SaleService.get_sale(sale_id)
        if not original_sale:
            raise ValueError(f"Sale with id {sale_id} not found")

        query = '''
            UPDATE sales 
            SET customer_id = ?, date = ?, total_amount = ?
            WHERE id = ?
        '''
        DatabaseManager.execute_query(query, (
            updated_sale_data['customer_id'],
            updated_sale_data['date'],
            sum(item['price'] * item['quantity'] for item in updated_sale_data['items']),
            sale_id
        ))

        original_items = SaleService.get_sale_items(sale_id)
        DatabaseManager.execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))

        for item in updated_sale_data['items']:
            query = '''
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (sale_id, item['product_id'], item['quantity'], item['price']))

        inventory_service = InventoryService()
        for original_item in original_items:
            inventory_service.update_quantity(original_item.product_id, original_item.quantity)
        for new_item in updated_sale_data['items']:
            inventory_service.update_quantity(new_item['product_id'], -new_item['quantity'])