from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.purchase import Purchase, PurchaseItem
from services.inventory_service import InventoryService
from utils.decorators import db_operation, validate_input
from utils.exceptions import ValidationException
from functools import lru_cache

class PurchaseService:
    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def create_purchase(supplier: str, date: str, items: List[Dict[str, Any]]) -> Optional[int]:
        total_amount = sum(item['quantity'] * item['cost_price'] for item in items)
        
        query = 'INSERT INTO purchases (supplier, date, total_amount) VALUES (?, ?, ?)'
        cursor = DatabaseManager.execute_query(query, (supplier, date, total_amount))
        purchase_id = cursor.lastrowid
        
        if purchase_id is None:
            raise ValidationException("Failed to create purchase record")

        for item in items:
            query = '''
                INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (purchase_id, item['product_id'], item['quantity'], item['cost_price']))
            
            update_query = 'UPDATE products SET cost_price = ? WHERE id = ?'
            DatabaseManager.execute_query(update_query, (item['cost_price'], item['product_id']))
            
            InventoryService.update_quantity(item['product_id'], item['quantity'])
        
        PurchaseService.clear_cache()
        return purchase_id

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase(purchase_id: int) -> Optional[Purchase]:
        query = 'SELECT * FROM purchases WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (purchase_id,))
        if row:
            purchase = Purchase.from_db_row(row)
            purchase.items = PurchaseService.get_purchase_items(purchase_id)
            return purchase
        return None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    def get_all_purchases() -> List[Purchase]:
        query = 'SELECT * FROM purchases ORDER BY date DESC'
        rows = DatabaseManager.fetch_all(query)
        purchases = [Purchase.from_db_row(row) for row in rows]
        for purchase in purchases:
            purchase.items = PurchaseService.get_purchase_items(purchase.id)
        return purchases

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_items(purchase_id: int) -> List[PurchaseItem]:
        query = 'SELECT * FROM purchase_items WHERE purchase_id = ?'
        rows = DatabaseManager.fetch_all(query, (purchase_id,))
        return [PurchaseItem.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    def delete_purchase(purchase_id: int) -> None:
        items = PurchaseService.get_purchase_items(purchase_id)
        
        for item in items:
            InventoryService.update_quantity(item.product_id, -item.quantity)
        
        DatabaseManager.execute_query('DELETE FROM purchase_items WHERE purchase_id = ?', (purchase_id,))
        DatabaseManager.execute_query('DELETE FROM purchases WHERE id = ?', (purchase_id,))
        PurchaseService.clear_cache()

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    def get_suppliers() -> List[str]:
        query = 'SELECT DISTINCT supplier FROM purchases'
        rows = DatabaseManager.fetch_all(query)
        return [row['supplier'] for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def update_purchase(purchase_id: int, supplier: str, date: str, items: List[Dict[str, Any]]) -> None:
        old_items = PurchaseService.get_purchase_items(purchase_id)
        
        for item in old_items:
            InventoryService.update_quantity(item.product_id, -item.quantity)
        
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        query = 'UPDATE purchases SET supplier = ?, date = ?, total_amount = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (supplier, date, total_amount, purchase_id))
        
        DatabaseManager.execute_query('DELETE FROM purchase_items WHERE purchase_id = ?', (purchase_id,))
        
        for item in items:
            query = '''
                INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (purchase_id, item['product_id'], item['quantity'], item['price']))
            InventoryService.update_quantity(item['product_id'], item['quantity'])
        
        PurchaseService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_stats(start_date: str, end_date: str) -> Dict[str, Any]:
        query = '''
        SELECT 
            COUNT(DISTINCT p.id) as total_purchases,
            SUM(p.total_amount) as total_amount,
            AVG(p.total_amount) as average_purchase_amount,
            COUNT(DISTINCT p.supplier) as unique_suppliers
        FROM purchases p
        WHERE p.date BETWEEN ? AND ?
        '''
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        return {
            'total_purchases': result['total_purchases'] if result else 0,
            'total_amount': float(result['total_amount']) if result and result['total_amount'] else 0.0,
            'average_purchase_amount': float(result['average_purchase_amount']) if result and result['average_purchase_amount'] else 0.0,
            'unique_suppliers': result['unique_suppliers'] if result else 0
        }

    @staticmethod
    def clear_cache():
        PurchaseService.get_all_purchases.cache_clear()
        PurchaseService.get_suppliers.cache_clear()
