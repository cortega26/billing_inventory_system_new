from functools import lru_cache
from typing import Any, Dict, List, Optional

from database.database_manager import DatabaseManager
from models.enums import TimeInterval
from models.purchase import Purchase, PurchaseItem
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, ValidationException
from utils.system.logger import logger
from utils.validation.validators import (
    validate_date,
    validate_integer,
    validate_string,
)


class PurchaseQueryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_purchase(purchase_id: int) -> Optional[Purchase]:
        purchase_id = validate_integer(purchase_id, min_value=1)
        row = DatabaseManager.fetch_one("SELECT * FROM purchases WHERE id = ?", (purchase_id,))
        if row:
            purchase = Purchase.from_db_row(row)
            purchase.items = PurchaseQueryService.get_purchase_items(purchase_id)
            logger.info("Purchase retrieved", extra={"purchase_id": purchase_id})
            return purchase

        logger.warning("Purchase not found", extra={"purchase_id": purchase_id})
        return None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_purchases() -> List[Purchase]:
        rows = DatabaseManager.fetch_all("SELECT * FROM purchases ORDER BY date DESC")
        purchases = PurchaseQueryService._hydrate_purchases(rows)
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
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_suppliers() -> List[str]:
        rows = DatabaseManager.fetch_all("SELECT DISTINCT supplier FROM purchases")
        suppliers = [row["supplier"] for row in rows]
        logger.info("Suppliers retrieved", extra={"count": len(suppliers)})
        return suppliers

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
    ) -> List[Dict[str, Any]]:
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

    @staticmethod
    @db_operation(show_dialog=True)
    def get_supplier_purchases(supplier: str) -> List[Purchase]:
        supplier = validate_string(supplier, min_length=1, max_length=100)
        rows = DatabaseManager.fetch_all(
            "SELECT * FROM purchases WHERE supplier = ? ORDER BY date DESC",
            (supplier,),
        )
        return PurchaseQueryService._hydrate_purchases(rows)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_statistics(start_date: str, end_date: str) -> Dict[str, Any]:
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
                "suppliers": PurchaseQueryService.get_suppliers(),
            }
        return {
            "total_purchases": row["total_purchases"],
            "total_amount": row["total_amount"],
            "suppliers": PurchaseQueryService.get_suppliers(),
        }

    @staticmethod
    @db_operation(show_dialog=True)
    def get_purchase_history(start_date: str, end_date: str) -> List[Purchase]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        if start_date > end_date:
            raise ValidationException("start_date must be before or equal to end_date")
        rows = DatabaseManager.fetch_all(
            "SELECT * FROM purchases WHERE date BETWEEN ? AND ? ORDER BY date DESC",
            (start_date, end_date),
        )
        return PurchaseQueryService._hydrate_purchases(rows)

    @staticmethod
    def clear_cache() -> None:
        PurchaseQueryService.get_all_purchases.cache_clear()
        PurchaseQueryService.get_suppliers.cache_clear()
        logger.debug("Purchase query cache cleared")

    @staticmethod
    def _hydrate_purchases(rows: List[Any]) -> List[Purchase]:
        if not rows:
            return []

        purchases = [Purchase.from_db_row(row) for row in rows]
        items_by_purchase = PurchaseQueryService._load_items_by_purchase(
            [purchase.id for purchase in purchases]
        )
        for purchase in purchases:
            purchase.items = items_by_purchase.get(purchase.id, [])
        return purchases

    @staticmethod
    def _load_items_by_purchase(
        purchase_ids: List[int],
    ) -> Dict[int, List[PurchaseItem]]:
        if not purchase_ids:
            return {}

        placeholders = ",".join("?" * len(purchase_ids))
        rows = DatabaseManager.fetch_all(
            f"SELECT * FROM purchase_items WHERE purchase_id IN ({placeholders}) ORDER BY purchase_id, id",
            tuple(purchase_ids),
        )

        items_by_purchase: Dict[int, List[PurchaseItem]] = {}
        for item_row in rows:
            purchase_id = item_row["purchase_id"]
            if purchase_id not in items_by_purchase:
                items_by_purchase[purchase_id] = []
            items_by_purchase[purchase_id].append(PurchaseItem.from_db_row(item_row))
        return items_by_purchase