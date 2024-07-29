from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.inventory import Inventory
from utils.logger import logger

class InventoryService:
    @staticmethod
    def update_quantity(product_id: int, quantity_change: int) -> None:
        logger.debug(f"Updating quantity for product ID {product_id} by {quantity_change}")
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        inventory = DatabaseManager.fetch_one(query, (product_id,))
        
        if inventory:
            new_quantity = inventory['quantity'] + quantity_change
            query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
            DatabaseManager.execute_query(query, (new_quantity, product_id))
            logger.info(f"Updated quantity for product ID {product_id}. New quantity: {new_quantity}")
        else:
            query = 'INSERT INTO inventory (product_id, quantity) VALUES (?, ?)'
            DatabaseManager.execute_query(query, (product_id, quantity_change))
            logger.info(f"Created new inventory entry for product ID {product_id} with quantity {quantity_change}")

    @staticmethod
    def get_inventory(product_id: int) -> Optional[Inventory]:
        logger.debug(f"Fetching inventory for product ID {product_id}")
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        row = DatabaseManager.fetch_one(query, (product_id,))
        if row:
            return Inventory.from_db_row(row)
        logger.info(f"No inventory found for product ID {product_id}")
        return None

    @staticmethod
    def get_all_inventory() -> List[Dict[str, Any]]:
        logger.debug("Fetching all inventory")
        query = '''
            SELECT p.id as product_id, p.name as product_name, COALESCE(i.quantity, 0) as quantity
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
        '''
        return DatabaseManager.fetch_all(query)

    @staticmethod
    def set_quantity(product_id: int, quantity: int) -> None:
        logger.debug(f"Setting quantity for product ID {product_id} to {quantity}")
        query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
        DatabaseManager.execute_query(query, (quantity, product_id))
        logger.info(f"Set quantity for product ID {product_id} to {quantity}")

    @staticmethod
    def delete_inventory(product_id: int) -> None:
        logger.debug(f"Deleting inventory for product ID {product_id}")
        query = 'DELETE FROM inventory WHERE product_id = ?'
        DatabaseManager.execute_query(query, (product_id,))
        logger.info(f"Deleted inventory for product ID {product_id}")

    @staticmethod
    def get_low_stock_products(threshold: int = 10) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching low stock products (threshold: {threshold})")
        query = '''
            SELECT p.id as product_id, p.name as product_name, COALESCE(i.quantity, 0) as quantity
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE COALESCE(i.quantity, 0) <= ?
        '''
        return DatabaseManager.fetch_all(query, (threshold,))

    @staticmethod
    def get_inventory_value() -> float:
        logger.debug("Calculating total inventory value")
        query = '''
            SELECT SUM(i.quantity * COALESCE(pi.price, 0)) as total_value
            FROM inventory i
            LEFT JOIN (
                SELECT product_id, AVG(price) as price
                FROM purchase_items
                GROUP BY product_id
            ) pi ON i.product_id = pi.product_id
        '''
        result = DatabaseManager.fetch_one(query)
        total_value = result['total_value'] if result and result['total_value'] is not None else 0
        logger.info(f"Total inventory value: {total_value}")
        return float(total_value)

    @staticmethod
    def adjust_inventory(product_id: int, quantity: int, reason: str) -> None:
        logger.debug(f"Adjusting inventory for product ID {product_id} by {quantity}")
        InventoryService.update_quantity(product_id, quantity)
        query = 'INSERT INTO inventory_adjustments (product_id, quantity_change, reason, date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)'
        DatabaseManager.execute_query(query, (product_id, quantity, reason))
        logger.info(f"Recorded inventory adjustment for product ID {product_id}: {quantity} ({reason})")