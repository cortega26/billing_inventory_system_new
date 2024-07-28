from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.inventory import Inventory

class InventoryService:
    @staticmethod
    def update_quantity(product_id: int, quantity_change: int) -> None:
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        inventory = DatabaseManager.fetch_one(query, (product_id,))
        
        if inventory:
            new_quantity = inventory['quantity'] + quantity_change
            query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
            DatabaseManager.execute_query(query, (new_quantity, product_id))
        else:
            query = 'INSERT INTO inventory (product_id, quantity) VALUES (?, ?)'
            DatabaseManager.execute_query(query, (product_id, quantity_change))

    @staticmethod
    def get_inventory(product_id: int) -> Optional[Inventory]:
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        row = DatabaseManager.fetch_one(query, (product_id,))
        return Inventory.from_row(row) if row else None

    @staticmethod
    def get_all_inventory() -> List[Dict[str, Any]]:
        query = '''
            SELECT p.id as product_id, p.name as product_name, COALESCE(i.quantity, 0) as quantity
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
        '''
        return DatabaseManager.fetch_all(query)

    @staticmethod
    def set_quantity(product_id: int, quantity: int) -> None:
        query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
        DatabaseManager.execute_query(query, (quantity, product_id))

    @staticmethod
    def delete_inventory(product_id: int) -> None:
        query = 'DELETE FROM inventory WHERE product_id = ?'
        DatabaseManager.execute_query(query, (product_id,))