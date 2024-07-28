from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.purchase import Purchase, PurchaseItem
from services.inventory_service import InventoryService

class PurchaseService:
    @staticmethod
    def create_purchase(supplier: str, date: str, items: List[Dict[str, Any]]) -> Optional[int]:
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        query = 'INSERT INTO purchases (supplier, date, total_amount) VALUES (?, ?, ?)'
        cursor = DatabaseManager.execute_query(query, (supplier, date, total_amount))
        purchase_id = cursor.lastrowid
        
        if purchase_id is None:
            return None

        for item in items:
            query = '''
                INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (purchase_id, item['product_id'], item['quantity'], item['price']))
            
            InventoryService.update_quantity(item['product_id'], item['quantity'])
        
        return purchase_id

    @staticmethod
    def get_purchase(purchase_id: int) -> Optional[Purchase]:
        query = 'SELECT * FROM purchases WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (purchase_id,))
        return Purchase.from_row(row) if row else None

    @staticmethod
    def get_all_purchases() -> List[Purchase]:
        query = 'SELECT * FROM purchases'
        rows = DatabaseManager.fetch_all(query)
        return [Purchase.from_row(row) for row in rows]

    @staticmethod
    def get_purchase_items(purchase_id: int) -> List[PurchaseItem]:
        query = 'SELECT * FROM purchase_items WHERE purchase_id = ?'
        rows = DatabaseManager.fetch_all(query, (purchase_id,))
        return [PurchaseItem.from_row(row) for row in rows]

    @staticmethod
    def delete_purchase(purchase_id: int) -> None:
        items = PurchaseService.get_purchase_items(purchase_id)
        
        for item in items:
            InventoryService.update_quantity(item.product_id, -item.quantity)
        
        DatabaseManager.execute_query('DELETE FROM purchase_items WHERE purchase_id = ?', (purchase_id,))
        DatabaseManager.execute_query('DELETE FROM purchases WHERE id = ?', (purchase_id,))

    @staticmethod
    def get_suppliers() -> List[str]:
        query = 'SELECT DISTINCT supplier FROM purchases'
        rows = DatabaseManager.fetch_all(query)
        return [row['supplier'] for row in rows]