from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.purchase import Purchase, PurchaseItem
from services.inventory_service import InventoryService
from utils.validation.validators import validate_string, validate_date, validate_integer
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import ValidationException, NotFoundException, DatabaseException
from utils.system.logger import logger
from utils.system.event_system import event_system
from functools import lru_cache

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
        total_amount = sum(item["quantity"] * item["cost_price"] for item in items)

        purchase_id = PurchaseService._insert_purchase(supplier, date, total_amount)

        if purchase_id is None:
            raise ValidationException("Failed to create purchase record")

        PurchaseService._insert_purchase_items(purchase_id, items)
        PurchaseService._update_inventory(items)

        logger.info("Purchase created", extra={"purchase_id": purchase_id, "supplier": supplier, "total_amount": total_amount})
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

        for item in items:
            InventoryService.update_quantity(item.product_id, -item.quantity)

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

        PurchaseService._revert_inventory(old_items)

        total_amount = sum(item["price"] * item["quantity"] for item in items)

        PurchaseService._update_purchase(purchase_id, supplier, date, total_amount)
        PurchaseService._update_purchase_items(purchase_id, items)
        PurchaseService._update_inventory(items)

        logger.info("Purchase updated", extra={"purchase_id": purchase_id, "supplier": supplier, "total_amount": total_amount})
        PurchaseService.clear_cache()
        event_system.purchase_updated.emit(purchase_id)

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchase_stats(start_date: str, end_date: str) -> Dict[str, Any]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
        SELECT 
            COUNT(DISTINCT p.id) as total_purchases,
            SUM(p.total_amount) as total_amount,
            AVG(p.total_amount) as average_purchase_amount,
            COUNT(DISTINCT p.supplier) as unique_suppliers
        FROM purchases p
        WHERE p.date BETWEEN ? AND ?
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        stats = {
            "total_purchases": result["total_purchases"] if result else 0,
            "total_amount": float(result["total_amount"]) if result and result["total_amount"] else 0.0,
            "average_purchase_amount": float(result["average_purchase_amount"]) if result and result["average_purchase_amount"] else 0.0,
            "unique_suppliers": result["unique_suppliers"] if result else 0,
        }
        logger.info("Purchase stats retrieved", extra={"start_date": start_date, "end_date": end_date, "stats": stats})
        return stats

    @staticmethod
    def clear_cache():
        PurchaseService.get_all_purchases.cache_clear()
        PurchaseService.get_suppliers.cache_clear()
        logger.debug("Purchase cache cleared")

    @staticmethod
    def _validate_purchase_items(items: List[Dict[str, Any]]) -> None:
        if not items:
            raise ValidationException("Purchase must have at least one item")
        for item in items:
            if item["quantity"] <= 0 or item["cost_price"] <= 0:
                raise ValidationException(
                    "Item quantity and cost price must be positive"
                )

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_purchase(
        supplier: str, date: str, total_amount: float
    ) -> Optional[int]:
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
            DatabaseManager.execute_query(
                query,
                (purchase_id, item["product_id"], item["quantity"], item["cost_price"]),
            )

            update_query = "UPDATE products SET cost_price = ? WHERE id = ?"
            DatabaseManager.execute_query(
                update_query, (item["cost_price"], item["product_id"])
            )

    @staticmethod
    def _update_inventory(items: List[Dict[str, Any]]) -> None:
        for item in items:
            InventoryService.update_quantity(item["product_id"], item["quantity"])

    @staticmethod
    def _revert_inventory(items: List[PurchaseItem]) -> None:
        for item in items:
            InventoryService.update_quantity(item.product_id, -item.quantity)

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_purchase(
        purchase_id: int, supplier: str, date: str, total_amount: float
    ) -> None:
        query = "UPDATE purchases SET supplier = ?, date = ?, total_amount = ? WHERE id = ?"
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
    def get_purchases_by_supplier(supplier: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
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
        purchases = [{"id": row["id"], "date": row["date"], "total_amount": row["total_amount"]} for row in rows]
        logger.info("Purchases by supplier retrieved", extra={"supplier": supplier, "start_date": start_date, "end_date": end_date, "count": len(purchases)})
        return purchases

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchase_trends(start_date: str, end_date: str, interval: str = 'month') -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        interval = validate_string(interval, max_length=10)
        if interval not in ['day', 'week', 'month']:
            raise ValidationException("Invalid interval. Must be 'day', 'week', or 'month'")

        date_format = {
            'day': '%Y-%m-%d',
            'week': '%Y-%W',
            'month': '%Y-%m'
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
        trends = [{"period": row["period"], "purchase_count": row["purchase_count"], "total_amount": row["total_amount"]} for row in rows]
        logger.info("Purchase trends retrieved", extra={"start_date": start_date, "end_date": end_date, "interval": interval, "count": len(trends)})
        return trends
