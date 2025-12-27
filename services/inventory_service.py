from functools import lru_cache
from typing import Any, Dict, List, Optional

from database.database_manager import DatabaseManager
from models.enums import InventoryAction, QUANTITY_PRECISION
from models.inventory import Inventory
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import (
    DatabaseException,
    NotFoundException,
    UIException,
    ValidationException,
)
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.validators import (
    validate_float,
    validate_float_non_negative,
    validate_integer,
    validate_string,
)


class InventoryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_quantity(product_id: int, quantity_change: float) -> None:
        """Update the quantity of a product in inventory."""
        product_id = validate_integer(product_id, min_value=1)
        quantity_change = validate_float(
            quantity_change
        )  # Allow negative values for sales

        inventory = InventoryService.get_inventory(product_id)

        if inventory:
            # Round to precision
            new_quantity = round(inventory.quantity + quantity_change, QUANTITY_PRECISION)
            if new_quantity < 0:
                logger.warning(
                    f"Attempted negative inventory for product {product_id}. Current: {inventory.quantity}, Change: {quantity_change}, New: {new_quantity}",
                )
                raise ValidationException(
                    f"Inventory cannot be negative. Product: {product_id}, Current: {inventory.quantity}, Change: {quantity_change}, New: {new_quantity}"
                )
            InventoryService._modify_inventory(
                product_id, new_quantity, action=InventoryAction.UPDATE
            )
        else:
            if quantity_change < 0:
                raise ValidationException(
                    f"Cannot decrease quantity for non-existent inventory item. Product ID: {product_id}"
                )
            # When creating a new inventory record:
            new_quantity = round(quantity_change, QUANTITY_PRECISION)
            InventoryService._modify_inventory(
                product_id, new_quantity, action=InventoryAction.CREATE
            )

        InventoryService.clear_cache()
        event_system.inventory_changed.emit(product_id)
        logger.info(
            f"Inventory updated for product {product_id}",
            extra={"quantity_change": quantity_change, "new_quantity": new_quantity},
        )

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def _modify_inventory(product_id: int, new_quantity: float, action: InventoryAction) -> None:
        """Internal method to modify inventory based on action."""
        product_id = validate_integer(product_id, min_value=1)
        new_quantity = validate_float_non_negative(new_quantity)

        if action == InventoryAction.UPDATE:
            query = "UPDATE inventory SET quantity = ? WHERE product_id = ?"
            DatabaseManager.execute_query(query, (new_quantity, product_id))
            logger.debug(
                "Inventory quantity updated",
                extra={"product_id": product_id, "new_quantity": new_quantity},
            )
        elif action == InventoryAction.CREATE:
            query = "INSERT INTO inventory (product_id, quantity) VALUES (?, ?)"
            DatabaseManager.execute_query(query, (product_id, new_quantity))
            logger.debug(
                "New inventory item created",
                extra={"product_id": product_id, "initial_quantity": new_quantity},
            )
        else:
            logger.error(f"Unknown action: {action}")
            raise ValueError(f"Unknown action: {action}")

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
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def get_all_inventory() -> List[Dict[str, Any]]:
        """Get all inventory items with product and category details."""
        query = """
            SELECT 
                i.product_id,
                i.quantity,
                p.name as product_name,
                p.barcode,
                p.category_id,
                COALESCE(c.name, 'Uncategorized') as category_name
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.name
        """

        try:
            rows = DatabaseManager.fetch_all(query)
            inventory_items = []

            for row in rows:
                item = {
                    "product_id": row["product_id"],
                    "product_name": row["product_name"],
                    "category_id": row["category_id"],  # Added category_id
                    "category_name": row["category_name"],
                    "quantity": float(row["quantity"]),
                    "barcode": row["barcode"] or "No barcode",
                }
                inventory_items.append(item)

            return inventory_items

        except Exception as e:
            logger.error(f"Error fetching inventory: {str(e)}")
            raise DatabaseException(f"Failed to fetch inventory: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def set_quantity(product_id: int, new_quantity: float) -> None:
        """Set the quantity of a product in inventory to a specific value."""
        product_id = validate_integer(product_id, min_value=1)
        new_quantity = validate_float_non_negative(new_quantity)
        new_quantity = round(new_quantity, QUANTITY_PRECISION)

        InventoryService._modify_inventory(product_id, new_quantity, action=InventoryAction.UPDATE)

        event_system.inventory_updated.emit()
        InventoryService.clear_cache()
        logger.info(
            "Inventory quantity set",
            extra={"product_id": product_id, "new_quantity": new_quantity},
        )

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
    def get_inventory_value() -> int:
        query = """
            SELECT SUM(i.quantity * COALESCE(p.cost_price, 0)) as total_value
            FROM inventory i
            JOIN products p ON i.product_id = p.id
        """
        result = DatabaseManager.fetch_one(query)
        # Round to nearest integer since we're dealing with Chilean Pesos
        total_value = int(
            round(
                float(
                    result["total_value"]
                    if result and result["total_value"] is not None
                    else 0
                )
            )
        )
        logger.info(
            "Total inventory value calculated", extra={"total_value": total_value}
        )
        return total_value

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def adjust_inventory(product_id: int, quantity_change: float, reason: str) -> None:
        """Adjust the quantity of a product in inventory by a specific amount."""
        product_id = validate_integer(product_id, min_value=1)
        quantity_change = validate_float(
            quantity_change
        )  # Can be negative for adjustments
        reason = validate_string(reason, max_length=255)

        # Round to precision
        quantity_change = round(quantity_change, QUANTITY_PRECISION)

        InventoryService.update_quantity(product_id, quantity_change)

        query = """
            INSERT INTO inventory_adjustments (product_id, quantity_change, reason, date) 
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """
        DatabaseManager.execute_query(query, (product_id, str(quantity_change), reason))
        InventoryService.clear_cache()
        logger.info(
            "Inventory adjusted",
            extra={
                "product_id": product_id,
                "quantity_change": quantity_change,
                "reason": reason,
            },
        )

    @staticmethod
    def clear_cache() -> None:
        """Clear the inventory cache."""
        logger.debug("Clearing inventory cache")
        InventoryService.get_all_inventory.cache_clear()

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_inventory_movements(
        product_id: int, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        product_id = validate_integer(product_id, min_value=1)
        start_date = validate_string(start_date)
        end_date = validate_string(end_date)
        query = """
            SELECT 'adjustment' as type, date, quantity_change, reason
            FROM inventory_adjustments
            WHERE product_id = ? AND date BETWEEN ? AND ?
            UNION ALL
            SELECT 'sale' as type, s.date, -si.quantity as quantity_change, 
                   'Sale' as reason
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE si.product_id = ? AND s.date BETWEEN ? AND ?
            UNION ALL
            SELECT 'purchase' as type, p.date, pi.quantity as quantity_change, 
                   'Purchase' as reason
            FROM purchase_items pi
            JOIN purchases p ON pi.purchase_id = p.id
            WHERE pi.product_id = ? AND p.date BETWEEN ? AND ?
            ORDER BY date
        """
        params = (product_id, start_date, end_date) * 3
        result = DatabaseManager.fetch_all(query, params)
        logger.info(
            "Inventory movements retrieved",
            extra={
                "product_id": product_id,
                "start_date": start_date,
                "end_date": end_date,
                "count": len(result),
            },
        )
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
        turnover_ratios = {
            row["product_id"]: round(float(row["turnover_ratio"]), 3) for row in result
        }
        logger.info(
            "Inventory turnover calculated",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "product_count": len(turnover_ratios),
            },
        )
        return turnover_ratios

    @staticmethod
    def get_low_stock_products() -> List[Dict[str, Any]]:
        query = """
            SELECT p.id, p.name, i.quantity
            FROM products p
            JOIN inventory i ON p.id = i.product_id
            WHERE i.quantity < 10
        """
        products = DatabaseManager.fetch_all(query)
        logger.debug("Retrieved low stock products", extra={"count": len(products)})
        return products
