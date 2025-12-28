from functools import lru_cache
from typing import Any, Dict, List, Optional

from database.database_manager import DatabaseManager
from models.purchase import Purchase, PurchaseItem
from services.inventory_service import InventoryService
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, NotFoundException, ValidationException
from utils.system.event_system import event_system
from utils.system.logger import logger
from models.enums import MAX_PURCHASE_ITEMS, QUANTITY_PRECISION, TimeInterval, MAX_PRICE_CLP
from utils.validation.validators import (
    validate_date,
    validate_integer,
    validate_string,
)
from utils.math.financial_calculator import FinancialCalculator


class PurchaseService:
    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_purchase(
        supplier: str, date: str, items: List[Dict[str, Any]]
    ) -> Optional[int]:
        supplier = validate_string(supplier, max_length=100)
        date = validate_date(date)
        PurchaseService._validate_purchase_items(items)

        # Calculate total amount with proper integer handling for money
        total_amount = sum(
            FinancialCalculator.calculate_item_total(item["quantity"], item["cost_price"]) for item in items
        )

        purchase_id = PurchaseService._insert_purchase(supplier, date, total_amount)

        if purchase_id is None:
            raise ValidationException("Failed to create purchase record")

        PurchaseService._insert_purchase_items(purchase_id, items)
        InventoryService.apply_batch_updates(items, multiplier=1.0)

        logger.info(
            "Purchase created",
            extra={
                "purchase_id": purchase_id,
                "supplier": supplier,
                "total_amount": total_amount,
            },
        )
        PurchaseService.clear_cache()
        event_system.purchase_added.emit(purchase_id)
        return purchase_id

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_purchase(purchase_id: int) -> Optional[Purchase]:
        purchase_id = validate_integer(purchase_id, min_value=1)
        query = "SELECT * FROM purchases WHERE id = ?"
        row = DatabaseManager.fetch_one(query, (purchase_id,))
        if row:
            purchase = Purchase.from_db_row(row)
            purchase.items = PurchaseService.get_purchase_items(purchase_id)
            logger.info("Purchase retrieved", extra={"purchase_id": purchase_id})
            return purchase
        else:
            logger.warning("Purchase not found", extra={"purchase_id": purchase_id})
            raise NotFoundException(f"Purchase with ID {purchase_id} not found")

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_purchases() -> List[Purchase]:
        query = "SELECT * FROM purchases ORDER BY date DESC"
        rows = DatabaseManager.fetch_all(query)
        purchases = [Purchase.from_db_row(row) for row in rows]
        for purchase in purchases:
            purchase.items = PurchaseService.get_purchase_items(purchase.id)
        logger.info("All purchases retrieved", extra={"count": len(purchases)})
        return purchases

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchase_items(purchase_id: int) -> List[PurchaseItem]:
        purchase_id = validate_integer(purchase_id, min_value=1)
        query = "SELECT * FROM purchase_items WHERE purchase_id = ?"
        rows = DatabaseManager.fetch_all(query, (purchase_id,))
        return [PurchaseItem.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_purchase(purchase_id: int) -> None:
        purchase_id = validate_integer(purchase_id, min_value=1)
        items = PurchaseService.get_purchase_items(purchase_id)

        InventoryService.apply_batch_updates(items, multiplier=-1.0)

        DatabaseManager.execute_query(
            "DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,)
        )
        DatabaseManager.execute_query(
            "DELETE FROM purchases WHERE id = ?", (purchase_id,)
        )
        logger.info("Purchase deleted", extra={"purchase_id": purchase_id})
        PurchaseService.clear_cache()
        event_system.purchase_deleted.emit(purchase_id)

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_suppliers() -> List[str]:
        query = "SELECT DISTINCT supplier FROM purchases"
        rows = DatabaseManager.fetch_all(query)
        suppliers = [row["supplier"] for row in rows]
        logger.info("Suppliers retrieved", extra={"count": len(suppliers)})
        return suppliers

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_purchase(
        purchase_id: int, supplier: str, date: str, items: List[Dict[str, Any]]
    ) -> None:
        purchase_id = validate_integer(purchase_id, min_value=1)
        supplier = validate_string(supplier, max_length=100)
        date = validate_date(date)
        PurchaseService._validate_purchase_items(items)

        old_items = PurchaseService.get_purchase_items(purchase_id)
        InventoryService.apply_batch_updates(old_items, multiplier=-1.0)

        # Calculate total with proper rounding for money values
        total_amount = sum(
            FinancialCalculator.calculate_item_total(item["quantity"], item["cost_price"]) for item in items
        )

        PurchaseService._update_purchase(purchase_id, supplier, date, total_amount)
        PurchaseService._update_purchase_items(purchase_id, items)
        InventoryService.apply_batch_updates(items, multiplier=1.0)

        logger.info(
            "Purchase updated",
            extra={
                "purchase_id": purchase_id,
                "supplier": supplier,
                "total_amount": total_amount,
            },
        )
        PurchaseService.clear_cache()
        event_system.purchase_updated.emit(purchase_id)

    @staticmethod
    def _validate_purchase_items(items: List[Dict[str, Any]]) -> None:
        if not items:
            raise ValidationException("Purchase must have at least one item")
        if len(items) > MAX_PURCHASE_ITEMS:  # Prevent DOS attacks
            raise ValidationException(f"Too many items in single purchase (max {MAX_PURCHASE_ITEMS})")

        for item in items:
            try:
                # Sanitize inputs before any DB operation
                product_id = int(item.get("product_id", 0))
                if product_id <= 0 or product_id > 2147483647:  # SQLite INTEGER max
                    raise ValidationException(f"Invalid product ID: {product_id}")

                quantity = float(item.get("quantity", 0))
                if quantity <= 0 or quantity > 9999999.999:
                    raise ValidationException(f"Invalid quantity: {quantity}")
                
                if round(quantity, QUANTITY_PRECISION) != quantity:
                    raise ValidationException(f"Quantity cannot have more than {QUANTITY_PRECISION} decimal places")

                cost_price = int(item.get("cost_price", 0))
                if cost_price < 0 or cost_price > MAX_PRICE_CLP:
                    raise ValidationException(f"Invalid cost price: {cost_price}")

            except (ValueError, TypeError) as e:
                raise ValidationException(f"Invalid item data: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_purchase(supplier: str, date: str, total_amount: int) -> Optional[int]:
        query = "INSERT INTO purchases (supplier, date, total_amount) VALUES (?, ?, ?)"
        cursor = DatabaseManager.execute_query(query, (supplier, date, total_amount))
        return cursor.lastrowid

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_purchase_items(purchase_id: int, items: List[Dict[str, Any]]) -> None:
        for item in items:
            query = """
                INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            """
            # Store quantity with precision
            quantity_str = str(round(float(item["quantity"]), QUANTITY_PRECISION))
            DatabaseManager.execute_query(
                query,
                (purchase_id, item["product_id"], quantity_str, item["cost_price"]),
            )

            update_query = "UPDATE products SET cost_price = ? WHERE id = ?"
            DatabaseManager.execute_query(
                update_query, (item["cost_price"], item["product_id"])
            )

    # _update_inventory and _revert_inventory removed in favor of InventoryService.apply_batch_updates

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_purchase(
        purchase_id: int, supplier: str, date: str, total_amount: int
    ) -> None:
        query = (
            "UPDATE purchases SET supplier = ?, date = ?, total_amount = ? WHERE id = ?"
        )
        DatabaseManager.execute_query(
            query, (supplier, date, total_amount, purchase_id)
        )

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_purchase_items(purchase_id: int, items: List[Dict[str, Any]]) -> None:
        DatabaseManager.execute_query(
            "DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,)
        )
        PurchaseService._insert_purchase_items(purchase_id, items)

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchases_by_supplier(
        supplier: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        supplier = validate_string(supplier, max_length=100)
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT id, date, total_amount
            FROM purchases
            WHERE supplier = ? AND date BETWEEN ? AND ?
            ORDER BY date DESC
        """
        rows = DatabaseManager.fetch_all(query, (supplier, start_date, end_date))
        purchases = [
            {"id": row["id"], "date": row["date"], "total_amount": row["total_amount"]}
            for row in rows
        ]
        logger.info(
            "Purchases by supplier retrieved",
            extra={
                "supplier": supplier,
                "start_date": start_date,
                "end_date": end_date,
                "count": len(purchases),
            },
        )
        return purchases

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchase_trends(
        start_date: str, end_date: str, interval: str = "month"
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        interval = validate_string(interval, max_length=10)
        valid_intervals = [i.value for i in TimeInterval]
        if interval not in valid_intervals:
            raise ValidationException(
                f"Invalid interval. Must be one of {valid_intervals}"
            )

        date_format = {
            TimeInterval.DAY.value: "%Y-%m-%d",
            TimeInterval.WEEK.value: "%Y-%W",
            TimeInterval.MONTH.value: "%Y-%m"
        }

        query = f"""
            SELECT 
                strftime('{date_format[interval]}', date) as period,
                COUNT(*) as purchase_count,
                SUM(total_amount) as total_amount
            FROM purchases
            WHERE date BETWEEN ? AND ?
            GROUP BY period
            ORDER BY period
        """
        rows = DatabaseManager.fetch_all(query, (start_date, end_date))
        trends = [
            {
                "period": row["period"],
                "purchase_count": row["purchase_count"],
                "total_amount": row["total_amount"],
            }
            for row in rows
        ]
        logger.info(
            "Purchase trends retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "interval": interval,
                "count": len(trends),
            },
        )
        return trends

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_top_suppliers(
        start_date: str, end_date: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        limit = validate_integer(limit, min_value=1)
        query = """
            SELECT supplier, 
                   COUNT(*) as purchase_count, 
                   SUM(total_amount) as total_amount
            FROM purchases
            WHERE date BETWEEN ? AND ?
            GROUP BY supplier
            ORDER BY total_amount DESC
            LIMIT ?
        """
        rows = DatabaseManager.fetch_all(query, (start_date, end_date, limit))
        top_suppliers = [
            {
                "supplier": row["supplier"],
                "purchase_count": row["purchase_count"],
                "total_amount": row["total_amount"],
            }
            for row in rows
        ]
        logger.info(
            "Top suppliers retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "count": len(top_suppliers),
            },
        )
        return top_suppliers

    # void_purchase removed (alias for delete_purchase)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_supplier_purchases(supplier: str) -> List[Purchase]:
        """Get all purchases for a specific supplier."""
        query = "SELECT * FROM purchases WHERE supplier = ? ORDER BY date DESC"
        rows = DatabaseManager.fetch_all(query, (supplier,))
        purchases = [Purchase.from_db_row(row) for row in rows]
        for purchase in purchases:
            purchase.items = PurchaseService.get_purchase_items(purchase.id)
        return purchases

    # update_purchase_reference removed (unimplemented)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_statistics(start_date: str, end_date: str) -> Dict[str, Any]:
        """Get purchase statistics for a period."""
        query = """
            SELECT 
                COUNT(*) as total_purchases,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COUNT(DISTINCT supplier) as supplier_count
            FROM purchases
            WHERE date BETWEEN ? AND ?
        """
        row = DatabaseManager.fetch_one(query, (start_date, end_date))
        return {
            "total_purchases": row["total_purchases"],
            "total_amount": row["total_amount"],
            "suppliers": PurchaseService.get_suppliers(),
        }

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_history(start_date: str, end_date: str) -> List[Purchase]:
        """Get purchase history for a period."""
        query = "SELECT * FROM purchases WHERE date BETWEEN ? AND ? ORDER BY date DESC"
        rows = DatabaseManager.fetch_all(query, (start_date, end_date))
        purchases = [Purchase.from_db_row(row) for row in rows]
        for purchase in purchases:
            purchase.items = PurchaseService.get_purchase_items(purchase.id)
        return purchases

    @staticmethod
    def clear_cache():
        PurchaseService.get_all_purchases.cache_clear()
        PurchaseService.get_suppliers.cache_clear()
        logger.debug("Purchase cache cleared")
