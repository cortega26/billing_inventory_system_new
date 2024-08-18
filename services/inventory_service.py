from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.inventory import Inventory
from utils.system.event_system import event_system
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import ValidationException, NotFoundException, DatabaseException
from utils.validation.validators import validate_integer, validate_string, validate_int_non_negative, validate_float_non_negative
from utils.system.logger import logger
from functools import lru_cache

class InventoryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_quantity(product_id: int, quantity_change: int) -> None:
        product_id = validate_integer(product_id, min_value=1)
        quantity_change = validate_integer(quantity_change)

        inventory = InventoryService.get_inventory(product_id)

        if inventory:
            new_quantity = inventory.quantity + quantity_change
            if new_quantity < 0:
                raise ValidationException(
                    f"Insufficient inventory for product ID {product_id}. Current: {inventory.quantity}, Change: {quantity_change}"
                )
            InventoryService._update_inventory_quantity(product_id, new_quantity)
        else:
            if quantity_change < 0:
                raise ValidationException(
                    f"Cannot decrease quantity for non-existent inventory item. Product ID: {product_id}"
                )
            InventoryService._create_inventory_item(product_id, quantity_change)

        InventoryService.clear_cache()
        event_system.inventory_changed.emit(product_id)
        logger.info("Inventory updated", extra={"product_id": product_id, "quantity_change": quantity_change})

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_inventory(product_id: int) -> Optional[Inventory]:
        product_id = validate_integer(product_id, min_value=1)
        query = "SELECT * FROM inventory WHERE product_id = ?"
        row = DatabaseManager.fetch_one(query, (product_id,))
        if row:
            logger.info("Inventory retrieved", extra={"product_id": product_id})
            return Inventory.from_db_row(row)
        logger.warning("Inventory not found", extra={"product_id": product_id})
        return None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_inventory() -> List[Dict[str, Any]]:
        query = """
            SELECT i.product_id, p.name as product_name, 
                COALESCE(c.name, 'Uncategorized') as category_name, 
                i.quantity
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
        """
        result = DatabaseManager.fetch_all(query)
        logger.info("All inventory retrieved", extra={"count": len(result)})
        return result

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def set_quantity(product_id: int, quantity: float) -> None:
        product_id = validate_integer(product_id, min_value=1)
        quantity = validate_float_non_negative(quantity)
        
        InventoryService._update_inventory_quantity(product_id, quantity)
        InventoryService.clear_cache()
        event_system.inventory_changed.emit(product_id)
        logger.info("Inventory quantity set", extra={"product_id": product_id, "new_quantity": quantity})

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_inventory(product_id: int) -> None:
        product_id = validate_integer(product_id, min_value=1)
        query = "DELETE FROM inventory WHERE product_id = ?"
        DatabaseManager.execute_query(query, (product_id,))
        InventoryService.clear_cache()
        event_system.inventory_changed.emit(product_id)
        logger.info("Inventory deleted", extra={"product_id": product_id})

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_low_stock_products(threshold: int = 10) -> List[Dict[str, Any]]:
        threshold = validate_int_non_negative(threshold)
        query = """
            SELECT p.id as product_id, p.name as product_name, COALESCE(i.quantity, 0) as quantity
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE COALESCE(i.quantity, 0) <= ?
        """
        result = DatabaseManager.fetch_all(query, (threshold,))
        logger.info("Low stock products retrieved", extra={"threshold": threshold, "count": len(result)})
        return result

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_inventory_value() -> float:
        query = """
            SELECT SUM(i.quantity * COALESCE(p.cost_price, 0)) as total_value
            FROM inventory i
            JOIN products p ON i.product_id = p.id
        """
        result = DatabaseManager.fetch_one(query)
        total_value = float(result["total_value"] if result and result["total_value"] is not None else 0)
        logger.info("Total inventory value calculated", extra={"total_value": total_value})
        return total_value

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def adjust_inventory(product_id: int, quantity: int, reason: str) -> None:
        product_id = validate_integer(product_id, min_value=1)
        quantity = validate_integer(quantity)
        reason = validate_string(reason, max_length=255)
        
        InventoryService.update_quantity(product_id, quantity)
        query = "INSERT INTO inventory_adjustments (product_id, quantity_change, reason, date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)"
        DatabaseManager.execute_query(query, (product_id, quantity, reason))
        InventoryService.clear_cache()
        logger.info("Inventory adjusted", extra={"product_id": product_id, "quantity_change": quantity, "reason": reason})

    @staticmethod
    def clear_cache():
        InventoryService.get_all_inventory.cache_clear()
        logger.debug("Inventory cache cleared")

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_inventory_quantity(product_id: int, new_quantity: float) -> None:
        product_id = validate_integer(product_id, min_value=1)
        new_quantity = validate_float_non_negative(new_quantity)
        query = "UPDATE inventory SET quantity = ? WHERE product_id = ?"
        DatabaseManager.execute_query(query, (new_quantity, product_id))
        logger.debug("Inventory quantity updated", extra={"product_id": product_id, "new_quantity": new_quantity})

    @staticmethod
    @db_operation(show_dialog=True)
    def _create_inventory_item(product_id: int, quantity: float) -> None:
        product_id = validate_integer(product_id, min_value=1)
        quantity = validate_float_non_negative(quantity)
        query = "INSERT INTO inventory (product_id, quantity) VALUES (?, ?)"
        DatabaseManager.execute_query(query, (product_id, quantity))
        logger.debug("New inventory item created", extra={"product_id": product_id, "initial_quantity": quantity})

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_inventory_movements(product_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        product_id = validate_integer(product_id, min_value=1)
        start_date = validate_string(start_date)  # Assuming date is passed as a string
        end_date = validate_string(end_date)
        query = """
            SELECT 'adjustment' as type, date, quantity_change, reason
            FROM inventory_adjustments
            WHERE product_id = ? AND date BETWEEN ? AND ?
            UNION ALL
            SELECT 'sale' as type, s.date, -si.quantity as quantity_change, 'Sale' as reason
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE si.product_id = ? AND s.date BETWEEN ? AND ?
            UNION ALL
            SELECT 'purchase' as type, p.date, pi.quantity as quantity_change, 'Purchase' as reason
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            WHERE pi.product_id = ? AND p.date BETWEEN ? AND ?
            ORDER BY date
        """
        params = (product_id, start_date, end_date) * 3
        result = DatabaseManager.fetch_all(query, params)
        logger.info("Inventory movements retrieved", extra={"product_id": product_id, "start_date": start_date, "end_date": end_date, "count": len(result)})
        return result

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_inventory_turnover(start_date: str, end_date: str) -> Dict[int, float]:
        start_date = validate_string(start_date)
        end_date = validate_string(end_date)
        query = """
            WITH sales_data AS (
                SELECT si.product_id, SUM(si.quantity) as total_sold
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.date BETWEEN ? AND ?
                GROUP BY si.product_id
            ),
            avg_inventory AS (
                SELECT product_id, AVG(quantity) as avg_quantity
                FROM inventory
                GROUP BY product_id
            )
            SELECT sd.product_id, 
                   CASE WHEN ai.avg_quantity > 0 
                        THEN sd.total_sold / ai.avg_quantity 
                        ELSE 0 
                   END as turnover_ratio
            FROM sales_data sd
            JOIN avg_inventory ai ON sd.product_id = ai.product_id
        """
        result = DatabaseManager.fetch_all(query, (start_date, end_date))
        turnover_ratios = {row['product_id']: row['turnover_ratio'] for row in result}
        logger.info("Inventory turnover calculated", extra={"start_date": start_date, "end_date": end_date, "product_count": len(turnover_ratios)})
        return turnover_ratios
