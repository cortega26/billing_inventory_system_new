from functools import lru_cache
from typing import Any

from database.database_manager import DatabaseManager
from models.enums import (
    MAX_PRICE_CLP,
    MAX_PURCHASE_ITEMS,
    QUANTITY_PRECISION,
    TimeInterval,
)
from models.purchase import Purchase, PurchaseItem
from services.audit_service import AuditService
from services.inventory_service import InventoryService
from services.mutation_coordinator import MutationCoordinator
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, NotFoundException, ValidationException
from utils.helpers import get_product_ids_from_items
from utils.math.financial_calculator import FinancialCalculator
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.item_validators import validate_item_count, validate_line_item
from utils.validation.validators import (
    validate_date,
    validate_integer,
    validate_string,
)


class PurchaseService:
    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_purchase(
        supplier: str, date: str, items: list[dict[str, Any]]
    ) -> int | None:
        supplier = validate_string(supplier, max_length=100)
        date = validate_date(date)
        PurchaseService._validate_purchase_items(items)

        # Calculate total amount with proper integer handling for money
        total_amount = sum(
            FinancialCalculator.calculate_item_total(
                item["quantity"], item["cost_price"]
            )
            for item in items
        )

        with DatabaseManager.transaction():
            purchase_id = PurchaseService._insert_purchase(supplier, date, total_amount)

            if purchase_id is None:
                raise ValidationException("Failed to create purchase record")

            PurchaseService._insert_purchase_items(purchase_id, items)
            InventoryService.apply_batch_updates(
                items, multiplier=1.0, emit_events=False
            )
            AuditService.log_operation(
                "create_purchase",
                "purchase",
                purchase_id,
                {
                    "supplier": supplier,
                    "date": date,
                    "item_count": len(items),
                    "product_ids": get_product_ids_from_items(items),
                    "total_amount": total_amount,
                },
            )

        logger.info(
            "Purchase created",
            extra={
                "purchase_id": purchase_id,
                "supplier": supplier,
                "total_amount": total_amount,
            },
        )
        MutationCoordinator.finalize_mutation(
            entity_id=purchase_id,
            items=items,
            signal=event_system.purchase_added,
            service_cache_clear_fn=PurchaseService.clear_cache,
        )
        return purchase_id

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchase(purchase_id: int) -> Purchase | None:
        purchase_id = validate_integer(purchase_id, min_value=1)
        row = DatabaseManager.fetch_one(
            "SELECT * FROM purchases WHERE id = ?", (purchase_id,)
        )
        if row:
            purchase = Purchase.from_db_row(row)
            purchase.items = PurchaseService.get_purchase_items(purchase_id)
            logger.info("Purchase retrieved", extra={"purchase_id": purchase_id})
            return purchase

        logger.warning("Purchase not found", extra={"purchase_id": purchase_id})
        return None

    @staticmethod
    def _require_purchase(purchase_id: int) -> Purchase:
        purchase = PurchaseService.get_purchase(purchase_id)
        if purchase is not None:
            return purchase

        raise NotFoundException(f"Purchase with ID {purchase_id} not found")

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_purchases() -> list[Purchase]:
        rows = DatabaseManager.fetch_all("SELECT * FROM purchases ORDER BY date DESC")
        purchases = PurchaseService._hydrate_purchases(rows)
        logger.info("All purchases retrieved", extra={"count": len(purchases)})
        return purchases

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchase_items(purchase_id: int) -> list[PurchaseItem]:
        purchase_id = validate_integer(purchase_id, min_value=1)
        query = "SELECT * FROM purchase_items WHERE purchase_id = ?"
        rows = DatabaseManager.fetch_all(query, (purchase_id,))
        return [PurchaseItem.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_purchase(purchase_id: int) -> None:
        purchase_id = validate_integer(purchase_id, min_value=1)
        purchase = PurchaseService._require_purchase(purchase_id)
        items = purchase.items

        with DatabaseManager.transaction():
            InventoryService.apply_batch_updates(
                items, multiplier=-1.0, emit_events=False
            )
            AuditService.log_operation(
                "delete_purchase",
                "purchase",
                purchase_id,
                {
                    "item_count": len(items),
                    "product_ids": get_product_ids_from_items(items),
                },
            )

            DatabaseManager.execute_query(
                "DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,)
            )
            DatabaseManager.execute_query(
                "DELETE FROM purchases WHERE id = ?", (purchase_id,)
            )
        logger.info("Purchase deleted", extra={"purchase_id": purchase_id})
        MutationCoordinator.finalize_mutation(
            entity_id=purchase_id,
            items=items,
            signal=event_system.purchase_deleted,
            service_cache_clear_fn=PurchaseService.clear_cache,
        )

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_suppliers() -> list[str]:
        rows = DatabaseManager.fetch_all("SELECT DISTINCT supplier FROM purchases")
        suppliers = [row["supplier"] for row in rows]
        logger.info("Suppliers retrieved", extra={"count": len(suppliers)})
        return suppliers

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_purchase(
        purchase_id: int, supplier: str, date: str, items: list[dict[str, Any]]
    ) -> None:
        purchase_id = validate_integer(purchase_id, min_value=1)
        supplier = validate_string(supplier, max_length=100)
        date = validate_date(date)
        PurchaseService._validate_purchase_items(items)

        purchase = PurchaseService._require_purchase(purchase_id)
        old_items = purchase.items

        # Calculate total with proper rounding for money values
        total_amount = sum(
            FinancialCalculator.calculate_item_total(
                item["quantity"], item["cost_price"]
            )
            for item in items
        )

        with DatabaseManager.transaction():
            InventoryService.apply_batch_updates(
                old_items, multiplier=-1.0, emit_events=False
            )
            PurchaseService._update_purchase(purchase_id, supplier, date, total_amount)
            PurchaseService._update_purchase_items(purchase_id, items)
            InventoryService.apply_batch_updates(
                items, multiplier=1.0, emit_events=False
            )
            AuditService.log_operation(
                "update_purchase",
                "purchase",
                purchase_id,
                {
                    "supplier": supplier,
                    "date": date,
                    "old_item_count": len(old_items),
                    "new_item_count": len(items),
                    "product_ids": get_product_ids_from_items([*old_items, *items]),
                    "total_amount": total_amount,
                },
            )

        logger.info(
            "Purchase updated",
            extra={
                "purchase_id": purchase_id,
                "supplier": supplier,
                "total_amount": total_amount,
            },
        )
        MutationCoordinator.finalize_mutation(
            entity_id=purchase_id,
            items=[*old_items, *items],
            signal=event_system.purchase_updated,
            service_cache_clear_fn=PurchaseService.clear_cache,
        )

    @staticmethod
    def _validate_purchase_items(items: list[dict[str, Any]]) -> None:
        validate_item_count(items, MAX_PURCHASE_ITEMS, "purchase")
        for item in items:
            validate_line_item(
                item,
                quantity_min=0.001,
                quantity_max=9999999.999,
                price_min=0,
                price_max=MAX_PRICE_CLP,
                price_key="cost_price",
            )

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_purchase(supplier: str, date: str, total_amount: int) -> int | None:
        query = "INSERT INTO purchases (supplier, date, total_amount) VALUES (?, ?, ?)"
        cursor = DatabaseManager.execute_query(query, (supplier, date, total_amount))
        return cursor.lastrowid

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_purchase_items(purchase_id: int, items: list[dict[str, Any]]) -> None:
        query = """
            INSERT INTO purchase_items (purchase_id, product_id, quantity, price)
            VALUES (?, ?, ?, ?)
        """
        # Store quantity as a number (not a string) for consistent typing
        batch_params = [
            (
                purchase_id,
                int(item["product_id"]),
                round(float(item["quantity"]), QUANTITY_PRECISION),
                int(item["cost_price"]),
            )
            for item in items
        ]
        DatabaseManager.executemany(query, batch_params)

    # _update_inventory and _revert_inventory removed in favor of InventoryService.apply_batch_updates

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_purchase(
        purchase_id: int, supplier: str, date: str, total_amount: int
    ) -> None:
        query = (
            "UPDATE purchases SET supplier = ?, date = ?, total_amount = ? WHERE id = ?"
        )
        cursor = DatabaseManager.execute_query(
            query, (supplier, date, total_amount, purchase_id)
        )
        if cursor.rowcount == 0:
            raise NotFoundException(f"Purchase with ID {purchase_id} not found")

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_purchase_items(purchase_id: int, items: list[dict[str, Any]]) -> None:
        DatabaseManager.execute_query(
            "DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,)
        )
        PurchaseService._insert_purchase_items(purchase_id, items)

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchases_by_supplier(
        supplier: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
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
    ) -> list[dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        interval = validate_string(interval, max_length=10)
        valid_intervals = [time_interval.value for time_interval in TimeInterval]
        if interval not in valid_intervals:
            raise ValidationException(
                f"Invalid interval. Must be one of {valid_intervals}"
            )

        date_format = {
            TimeInterval.DAY.value: "%Y-%m-%d",
            TimeInterval.WEEK.value: "%Y-%W",
            TimeInterval.MONTH.value: "%Y-%m",
        }
        rows = DatabaseManager.fetch_all(
            """
            SELECT
                strftime(?, date) as period,
                COUNT(*) as purchase_count,
                SUM(total_amount) as total_amount
            FROM purchases
            WHERE date BETWEEN ? AND ?
            GROUP BY period
            ORDER BY period
            """,
            (date_format[interval], start_date, end_date),
        )
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
    ) -> list[dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        limit = validate_integer(limit, min_value=1, max_value=1000)
        rows = DatabaseManager.fetch_all(
            """
            SELECT supplier,
                   COUNT(*) as purchase_count,
                   SUM(total_amount) as total_amount
            FROM purchases
            WHERE date BETWEEN ? AND ?
            GROUP BY supplier
            ORDER BY total_amount DESC
            LIMIT ?
            """,
            (start_date, end_date, limit),
        )
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
    def get_supplier_purchases(supplier: str) -> list[Purchase]:
        supplier = validate_string(supplier, min_length=1, max_length=100)
        rows = DatabaseManager.fetch_all(
            "SELECT * FROM purchases WHERE supplier = ? ORDER BY date DESC",
            (supplier,),
        )
        return PurchaseService._hydrate_purchases(rows)

    # update_purchase_reference removed (unimplemented)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_statistics(start_date: str, end_date: str) -> dict[str, Any]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        row = DatabaseManager.fetch_one(
            """
            SELECT
                COUNT(*) as total_purchases,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COUNT(DISTINCT supplier) as supplier_count
            FROM purchases
            WHERE date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        )
        if not row:
            return {
                "total_purchases": 0,
                "total_amount": 0,
                "suppliers": PurchaseService.get_suppliers(),
            }
        return {
            "total_purchases": row["total_purchases"],
            "total_amount": row["total_amount"],
            "suppliers": PurchaseService.get_suppliers(),
        }

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_history(start_date: str, end_date: str) -> list[Purchase]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        if start_date > end_date:
            raise ValidationException("start_date must be before or equal to end_date")
        rows = DatabaseManager.fetch_all(
            "SELECT * FROM purchases WHERE date BETWEEN ? AND ? ORDER BY date DESC",
            (start_date, end_date),
        )
        return PurchaseService._hydrate_purchases(rows)

    @staticmethod
    def _hydrate_purchases(rows: list[Any]) -> list[Purchase]:
        if not rows:
            return []

        purchases = [Purchase.from_db_row(row) for row in rows]
        items_by_purchase = PurchaseService._load_items_by_purchase(
            [purchase.id or 0 for purchase in purchases]
        )
        for purchase in purchases:
            purchase.items = items_by_purchase.get(purchase.id or 0, [])
        return purchases

    @staticmethod
    def _load_items_by_purchase(
        purchase_ids: list[int],
    ) -> dict[int, list[PurchaseItem]]:
        if not purchase_ids:
            return {}

        placeholders = ",".join("?" * len(purchase_ids))
        rows = DatabaseManager.fetch_all(
            f"SELECT * FROM purchase_items WHERE purchase_id IN ({placeholders}) ORDER BY purchase_id, id",  # nosec B608
            tuple(purchase_ids),
        )

        items_by_purchase: dict[int, list[PurchaseItem]] = {}
        for item_row in rows:
            purchase_id = item_row["purchase_id"]
            if purchase_id not in items_by_purchase:
                items_by_purchase[purchase_id] = []
            items_by_purchase[purchase_id].append(PurchaseItem.from_db_row(item_row))
        return items_by_purchase

    @classmethod
    def clear_cache(cls) -> None:
        PurchaseService.get_all_purchases.cache_clear()
        PurchaseService.get_suppliers.cache_clear()
        logger.debug("Purchase cache cleared")
