from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.inventory import Inventory
from utils.system.event_system import event_system
from utils.system.logger import logger
from functools import lru_cache

class InventoryService:
    @staticmethod
    def update_quantity(product_id: int, quantity_change: int) -> None:
        try:
            logger.debug(f"Updating quantity for product ID {product_id} by {quantity_change}")
            query = 'SELECT * FROM inventory WHERE product_id = ?'
            inventory = DatabaseManager.fetch_one(query, (product_id,))
            
            if inventory:
                new_quantity = inventory['quantity'] + quantity_change
                if new_quantity < 0:
                    raise ValueError(f"Insufficient inventory for product ID {product_id}. Current: {inventory['quantity']}, Change: {quantity_change}")
                query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
                DatabaseManager.execute_query(query, (new_quantity, product_id))
                logger.info(f"Updated quantity for product ID {product_id}. New quantity: {new_quantity}")
            else:
                if quantity_change < 0:
                    raise ValueError(f"Cannot decrease quantity for non-existent inventory item. Product ID: {product_id}")
                query = 'INSERT INTO inventory (product_id, quantity) VALUES (?, ?)'
                DatabaseManager.execute_query(query, (product_id, quantity_change))
                logger.info(f"Created new inventory entry for product ID {product_id} with quantity {quantity_change}")
            
            InventoryService.clear_cache()
            event_system.inventory_changed.emit(product_id)
        except Exception as e:
            logger.error(f"Error updating inventory quantity: {str(e)}")
            raise

    @staticmethod
    def get_inventory(product_id: int) -> Optional[Inventory]:
        try:
            logger.debug(f"Fetching inventory for product ID {product_id}")
            query = 'SELECT * FROM inventory WHERE product_id = ?'
            row = DatabaseManager.fetch_one(query, (product_id,))
            if row:
                return Inventory.from_db_row(row)
            logger.info(f"No inventory found for product ID {product_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting inventory: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=1)
    def get_all_inventory() -> List[Dict[str, Any]]:
        try:
            logger.debug("Fetching all inventory")
            query = '''
                SELECT i.product_id, p.name as product_name, 
                    COALESCE(c.name, 'Uncategorized') as category_name, 
                    i.quantity
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                LEFT JOIN categories c ON p.category_id = c.id
            '''
            return DatabaseManager.fetch_all(query)
        except Exception as e:
            logger.error(f"Error getting all inventory: {str(e)}")
            raise

    @staticmethod
    def set_quantity(product_id: int, quantity: int) -> None:
        try:
            logger.debug(f"Setting quantity for product ID {product_id} to {quantity}")
            if quantity < 0:
                raise ValueError(f"Cannot set negative quantity for product ID {product_id}")
            query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
            DatabaseManager.execute_query(query, (quantity, product_id))
            logger.info(f"Set quantity for product ID {product_id} to {quantity}")
            InventoryService.clear_cache()
        except Exception as e:
            logger.error(f"Error setting inventory quantity: {str(e)}")
            raise

    @staticmethod
    def delete_inventory(product_id: int) -> None:
        try:
            logger.debug(f"Deleting inventory for product ID {product_id}")
            query = 'DELETE FROM inventory WHERE product_id = ?'
            DatabaseManager.execute_query(query, (product_id,))
            logger.info(f"Deleted inventory for product ID {product_id}")
            InventoryService.clear_cache()
        except Exception as e:
            logger.error(f"Error deleting inventory: {str(e)}")
            raise

    @staticmethod
    def get_low_stock_products(threshold: int = 10) -> List[Dict[str, Any]]:
        try:
            logger.debug(f"Fetching low stock products (threshold: {threshold})")
            query = '''
                SELECT p.id as product_id, p.name as product_name, COALESCE(i.quantity, 0) as quantity
                FROM products p
                LEFT JOIN inventory i ON p.id = i.product_id
                WHERE COALESCE(i.quantity, 0) <= ?
            '''
            return DatabaseManager.fetch_all(query, (threshold,))
        except Exception as e:
            logger.error(f"Error getting low stock products: {str(e)}")
            raise

    @staticmethod
    def get_inventory_value() -> float:
        try:
            logger.debug("Calculating total inventory value")
            query = '''
                SELECT SUM(i.quantity * COALESCE(p.cost_price, 0)) as total_value
                FROM inventory i
                JOIN products p ON i.product_id = p.id
            '''
            result = DatabaseManager.fetch_one(query)
            total_value = result['total_value'] if result and result['total_value'] is not None else 0
            logger.info(f"Total inventory value: {total_value}")
            return float(total_value)
        except Exception as e:
            logger.error(f"Error calculating inventory value: {str(e)}")
            raise

    @staticmethod
    def adjust_inventory(product_id: int, quantity: int, reason: str) -> None:
        try:
            logger.debug(f"Adjusting inventory for product ID {product_id} by {quantity}")
            InventoryService.update_quantity(product_id, quantity)
            query = 'INSERT INTO inventory_adjustments (product_id, quantity_change, reason, date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)'
            DatabaseManager.execute_query(query, (product_id, quantity, reason))
            logger.info(f"Recorded inventory adjustment for product ID {product_id}: {quantity} ({reason})")
            InventoryService.clear_cache()
        except Exception as e:
            logger.error(f"Error adjusting inventory: {str(e)}")
            raise

    @staticmethod
    def clear_cache():
        InventoryService.get_all_inventory.cache_clear()
