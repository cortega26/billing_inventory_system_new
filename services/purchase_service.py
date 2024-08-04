from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.purchase import Purchase, PurchaseItem
from services.inventory_service import InventoryService
from utils.logger import logger
from datetime import datetime
from functools import lru_cache

class PurchaseService:
    @staticmethod
    def create_purchase(supplier: str, date: str, items: List[Dict[str, Any]]) -> Optional[int]:
        try:
            logger.debug(f"Creating purchase from {supplier} on {date} with {len(items)} items")
            total_amount = sum(item['quantity'] * item['cost_price'] for item in items)
            
            query = 'INSERT INTO purchases (supplier, date, total_amount) VALUES (?, ?, ?)'
            cursor = DatabaseManager.execute_query(query, (supplier, date, total_amount))
            purchase_id = cursor.lastrowid
            
            if purchase_id is None:
                raise ValueError("Failed to create purchase record")

            for item in items:
                query = '''
                    INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
                    VALUES (?, ?, ?, ?)
                '''
                DatabaseManager.execute_query(query, (purchase_id, item['product_id'], item['quantity'], item['cost_price']))
                
                # Update the product's cost_price
                update_query = 'UPDATE products SET cost_price = ? WHERE id = ?'
                DatabaseManager.execute_query(update_query, (item['cost_price'], item['product_id']))
                
                InventoryService.update_quantity(item['product_id'], item['quantity'])
            
            logger.info(f"Created purchase with ID: {purchase_id}")
            PurchaseService.clear_cache()
            return purchase_id
        except Exception as e:
            logger.error(f"Error creating purchase: {str(e)}")
            raise

    @staticmethod
    def get_purchase(purchase_id: int) -> Optional[Purchase]:
        try:
            logger.debug(f"Fetching purchase with ID: {purchase_id}")
            query = 'SELECT * FROM purchases WHERE id = ?'
            row = DatabaseManager.fetch_one(query, (purchase_id,))
            if row:
                purchase = Purchase.from_db_row(row)
                purchase.items = PurchaseService.get_purchase_items(purchase_id)
                logger.debug(f"Retrieved purchase: {purchase}")
                return purchase
            logger.debug(f"No purchase found with ID: {purchase_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting purchase: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=1)
    def get_all_purchases() -> List[Purchase]:
        try:
            logger.debug("Fetching all purchases")
            query = 'SELECT * FROM purchases ORDER BY date DESC'
            rows = DatabaseManager.fetch_all(query)
            purchases = [Purchase.from_db_row(row) for row in rows]
            for purchase in purchases:
                purchase.items = PurchaseService.get_purchase_items(purchase.id)
            logger.debug(f"Retrieved {len(purchases)} purchases")
            return purchases
        except Exception as e:
            logger.error(f"Error getting all purchases: {str(e)}")
            raise

    @staticmethod
    def get_purchase_items(purchase_id: int) -> List[PurchaseItem]:
        try:
            logger.debug(f"Fetching items for purchase ID: {purchase_id}")
            query = 'SELECT * FROM purchase_items WHERE purchase_id = ?'
            rows = DatabaseManager.fetch_all(query, (purchase_id,))
            items = [PurchaseItem.from_db_row(row) for row in rows]
            logger.debug(f"Retrieved {len(items)} items for purchase ID: {purchase_id}")
            return items
        except Exception as e:
            logger.error(f"Error getting purchase items: {str(e)}")
            raise

    @staticmethod
    def delete_purchase(purchase_id: int) -> None:
        try:
            logger.debug(f"Deleting purchase with ID: {purchase_id}")
            items = PurchaseService.get_purchase_items(purchase_id)
            
            for item in items:
                InventoryService.update_quantity(item.product_id, -item.quantity)
            
            DatabaseManager.execute_query('DELETE FROM purchase_items WHERE purchase_id = ?', (purchase_id,))
            DatabaseManager.execute_query('DELETE FROM purchases WHERE id = ?', (purchase_id,))
            logger.info(f"Deleted purchase with ID: {purchase_id}")
            PurchaseService.clear_cache()
        except Exception as e:
            logger.error(f"Error deleting purchase: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=1)
    def get_suppliers() -> List[str]:
        try:
            logger.debug("Fetching all suppliers")
            query = 'SELECT DISTINCT supplier FROM purchases'
            rows = DatabaseManager.fetch_all(query)
            suppliers = [row['supplier'] for row in rows]
            logger.debug(f"Retrieved {len(suppliers)} unique suppliers")
            return suppliers
        except Exception as e:
            logger.error(f"Error getting suppliers: {str(e)}")
            raise

    @staticmethod
    def update_purchase(purchase_id: int, supplier: str, date: str, items: List[Dict[str, Any]]) -> None:
        try:
            logger.debug(f"Updating purchase with ID: {purchase_id}")
            old_items = PurchaseService.get_purchase_items(purchase_id)
            
            # Revert inventory changes from old items
            for item in old_items:
                InventoryService.update_quantity(item.product_id, -item.quantity)
            
            total_amount = sum(item['price'] * item['quantity'] for item in items)
            
            query = 'UPDATE purchases SET supplier = ?, date = ?, total_amount = ? WHERE id = ?'
            DatabaseManager.execute_query(query, (supplier, date, total_amount, purchase_id))
            
            # Delete old items
            DatabaseManager.execute_query('DELETE FROM purchase_items WHERE purchase_id = ?', (purchase_id,))
            
            # Insert new items and update inventory
            for item in items:
                query = '''
                    INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
                    VALUES (?, ?, ?, ?)
                '''
                DatabaseManager.execute_query(query, (purchase_id, item['product_id'], item['quantity'], item['price']))
                InventoryService.update_quantity(item['product_id'], item['quantity'])
            
            logger.info(f"Updated purchase with ID: {purchase_id}")
            PurchaseService.clear_cache()
        except Exception as e:
            logger.error(f"Error updating purchase: {str(e)}")
            raise

    @staticmethod
    def get_purchase_stats(start_date: str, end_date: str) -> Dict[str, Any]:
        try:
            logger.debug(f"Fetching purchase stats from {start_date} to {end_date}")
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
            stats = {
                'total_purchases': result['total_purchases'] if result else 0,
                'total_amount': float(result['total_amount']) if result and result['total_amount'] else 0.0,
                'average_purchase_amount': float(result['average_purchase_amount']) if result and result['average_purchase_amount'] else 0.0,
                'unique_suppliers': result['unique_suppliers'] if result else 0
            }
            logger.debug(f"Purchase stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Error getting purchase stats: {str(e)}")
            raise

    @staticmethod
    def clear_cache():
        PurchaseService.get_all_purchases.cache_clear()
        PurchaseService.get_suppliers.cache_clear()