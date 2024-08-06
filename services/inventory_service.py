from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.inventory import Inventory
from utils.system.event_system import event_system
from utils.decorators import db_operation, validate_input
from utils.exceptions import ValidationException
from functools import lru_cache

class InventoryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def update_quantity(product_id: int, quantity_change: int) -> None:
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        inventory = DatabaseManager.fetch_one(query, (product_id,))
        
        if inventory:
            new_quantity = inventory['quantity'] + quantity_change
            if new_quantity < 0:
                raise ValidationException(f"Insufficient inventory for product ID {product_id}. Current: {inventory['quantity']}, Change: {quantity_change}")
            query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
            DatabaseManager.execute_query(query, (new_quantity, product_id))
        else:
            if quantity_change < 0:
                raise ValidationException(f"Cannot decrease quantity for non-existent inventory item. Product ID: {product_id}")
            query = 'INSERT INTO inventory (product_id, quantity) VALUES (?, ?)'
            DatabaseManager.execute_query(query, (product_id, quantity_change))
        
        InventoryService.clear_cache()
        event_system.inventory_changed.emit(product_id)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_inventory(product_id: int) -> Optional[Inventory]:
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        row = DatabaseManager.fetch_one(query, (product_id,))
        return Inventory.from_db_row(row) if row else None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    def get_all_inventory() -> List[Dict[str, Any]]:
        query = '''
            SELECT i.product_id, p.name as product_name, 
                COALESCE(c.name, 'Uncategorized') as category_name, 
                i.quantity
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
        '''
        return DatabaseManager.fetch_all(query)

    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def set_quantity(product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise ValidationException(f"Cannot set negative quantity for product ID {product_id}")
        query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
        DatabaseManager.execute_query(query, (quantity, product_id))
        InventoryService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def delete_inventory(product_id: int) -> None:
        query = 'DELETE FROM inventory WHERE product_id = ?'
        DatabaseManager.execute_query(query, (product_id,))
        InventoryService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def get_low_stock_products(threshold: int = 10) -> List[Dict[str, Any]]:
        query = '''
            SELECT p.id as product_id, p.name as product_name, COALESCE(i.quantity, 0) as quantity
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE COALESCE(i.quantity, 0) <= ?
        '''
        return DatabaseManager.fetch_all(query, (threshold,))

    @staticmethod
    @db_operation(show_dialog=True)
    def get_inventory_value() -> float:
        query = '''
            SELECT SUM(i.quantity * COALESCE(p.cost_price, 0)) as total_value
            FROM inventory i
            JOIN products p ON i.product_id = p.id
        '''
        result = DatabaseManager.fetch_one(query)
        return float(result['total_value'] if result and result['total_value'] is not None else 0)

    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def adjust_inventory(product_id: int, quantity: int, reason: str) -> None:
        InventoryService.update_quantity(product_id, quantity)
        query = 'INSERT INTO inventory_adjustments (product_id, quantity_change, reason, date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)'
        DatabaseManager.execute_query(query, (product_id, quantity, reason))
        InventoryService.clear_cache()

    @staticmethod
    def clear_cache():
        InventoryService.get_all_inventory.cache_clear()
