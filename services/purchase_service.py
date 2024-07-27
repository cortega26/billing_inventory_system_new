from database import execute_query, fetch_one, fetch_all
from models.purchase import Purchase, PurchaseItem
from services.inventory_service import InventoryService

class PurchaseService:
    @staticmethod
    def create_purchase(supplier, date, items):
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        query = 'INSERT INTO purchases (supplier, date, total_amount) VALUES (?, ?, ?)'
        cursor = execute_query(query, (supplier, date, total_amount))
        purchase_id = cursor.lastrowid
        
        for item in items:
            query = '''
                INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            execute_query(query, (purchase_id, item['product_id'], item['quantity'], item['price']))
            
            InventoryService.update_quantity(item['product_id'], item['quantity'])
        
        return purchase_id

    @staticmethod
    def get_purchase(purchase_id):
        query = 'SELECT * FROM purchases WHERE id = ?'
        row = fetch_one(query, (purchase_id,))
        return Purchase.from_row(row) if row else None

    @staticmethod
    def get_all_purchases():
        query = 'SELECT * FROM purchases'
        rows = fetch_all(query)
        return [Purchase.from_row(row) for row in rows]

    @staticmethod
    def get_purchase_items(purchase_id):
        query = 'SELECT * FROM purchase_items WHERE purchase_id = ?'
        rows = fetch_all(query, (purchase_id,))
        return [PurchaseItem.from_row(row) for row in rows]

    @staticmethod
    def delete_purchase(purchase_id):
        # Get purchase items
        items = PurchaseService.get_purchase_items(purchase_id)
        
        # Update inventory
        for item in items:
            InventoryService.update_quantity(item.product_id, -item.quantity)
        
        # Delete purchase items
        execute_query('DELETE FROM purchase_items WHERE purchase_id = ?', (purchase_id,))
        
        # Delete purchase
        execute_query('DELETE FROM purchases WHERE id = ?', (purchase_id,))

    @staticmethod
    def get_suppliers():
        query = 'SELECT DISTINCT supplier FROM purchases'
        rows = fetch_all(query)
        return [row['supplier'] for row in rows]