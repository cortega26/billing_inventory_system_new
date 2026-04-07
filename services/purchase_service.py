from typing import Any, Dict, List, Optional

from database.database_manager import DatabaseManager
from models.enums import (
    MAX_PRICE_CLP,
    MAX_PURCHASE_ITEMS,
    QUANTITY_PRECISION,
)
from models.purchase import Purchase
from services.audit_service import AuditService
from services.analytics_service import AnalyticsService
from services.inventory_service import InventoryService
from services.purchase_query_service import PurchaseQueryService
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, NotFoundException, ValidationException
from utils.math.financial_calculator import FinancialCalculator
from utils.system.event_system import event_system
from utils.system.logger import logger
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
        supplier: str, date: str, items: List[Dict[str, Any]]
    ) -> Optional[int]:
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
                    "product_ids": PurchaseService._get_product_ids(items),
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
        PurchaseService._finalize_purchase_mutation(
            purchase_id, items, event_system.purchase_added
        )
        return purchase_id

    @staticmethod
    def get_purchase(purchase_id: int) -> Optional[Purchase]:
        return PurchaseQueryService.get_purchase(purchase_id)

    @staticmethod
    def _require_purchase(purchase_id: int) -> Purchase:
        purchase = PurchaseService.get_purchase(purchase_id)
        if purchase is not None:
            return purchase

        raise NotFoundException(f"Purchase with ID {purchase_id} not found")

    @staticmethod
    def get_all_purchases() -> List[Purchase]:
        return PurchaseQueryService.get_all_purchases()

    @staticmethod
    def get_purchase_items(purchase_id: int):
        return PurchaseQueryService.get_purchase_items(purchase_id)

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
                    "product_ids": PurchaseService._get_product_ids(items),
                },
            )

            DatabaseManager.execute_query(
                "DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,)
            )
            DatabaseManager.execute_query(
                "DELETE FROM purchases WHERE id = ?", (purchase_id,)
            )
        logger.info("Purchase deleted", extra={"purchase_id": purchase_id})
        PurchaseService._finalize_purchase_mutation(
            purchase_id, items, event_system.purchase_deleted
        )

    @staticmethod
    def get_suppliers() -> List[str]:
        return PurchaseQueryService.get_suppliers()

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
                    "product_ids": PurchaseService._get_product_ids([*old_items, *items]),
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
        PurchaseService._finalize_purchase_mutation(
            purchase_id, [*old_items, *items], event_system.purchase_updated
        )

    @staticmethod
    def _validate_purchase_items(items: List[Dict[str, Any]]) -> None:
        if not items:
            raise ValidationException("Purchase must have at least one item")
        if len(items) > MAX_PURCHASE_ITEMS:  # Prevent DOS attacks
            raise ValidationException(
                f"Too many items in single purchase (max {MAX_PURCHASE_ITEMS})"
            )

        for item in items:
            PurchaseService._validate_purchase_item(item)

    @staticmethod
    def _validate_purchase_item(item: Dict[str, Any]) -> None:
        try:
            product_id = int(item.get("product_id", 0))
            if product_id <= 0 or product_id > 2147483647:
                raise ValidationException(f"Invalid product ID: {product_id}")

            quantity = float(item.get("quantity", 0))
            if quantity <= 0 or quantity > 9999999.999:
                raise ValidationException(f"Invalid quantity: {quantity}")

            if round(quantity, QUANTITY_PRECISION) != quantity:
                raise ValidationException(
                    f"Quantity cannot have more than {QUANTITY_PRECISION} decimal places"
                )

            cost_price = int(item.get("cost_price", 0))
            if cost_price < 0 or cost_price > MAX_PRICE_CLP:
                raise ValidationException(f"Invalid cost price: {cost_price}")
        except (ValueError, TypeError) as e:
            raise ValidationException(f"Invalid item data: {str(e)}")

    @staticmethod
    def _finalize_purchase_mutation(
        purchase_id: int, items: List[Any], signal: Any
    ) -> None:
        """Refresh caches and emit post-commit events for purchase mutations."""
        InventoryService.clear_cache()
        AnalyticsService.clear_cache()
        for product_id in PurchaseService._get_product_ids(items):
            event_system.inventory_changed.emit(product_id)
        PurchaseService.clear_cache()
        signal.emit(purchase_id)

    @staticmethod
    def _get_product_ids(items: List[Any]) -> List[int]:
        product_ids: List[int] = []
        for item in items:
            product_id = (
                item["product_id"]
                if isinstance(item, dict)
                else getattr(item, "product_id", None)
            )
            if product_id is not None and product_id not in product_ids:
                product_ids.append(int(product_id))
        return product_ids

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
    def _update_purchase_items(purchase_id: int, items: List[Dict[str, Any]]) -> None:
        DatabaseManager.execute_query(
            "DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,)
        )
        PurchaseService._insert_purchase_items(purchase_id, items)

    @staticmethod
    def get_purchases_by_supplier(
        supplier: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        return PurchaseQueryService.get_purchases_by_supplier(
            supplier, start_date, end_date
        )

    @staticmethod
    def get_purchase_trends(
        start_date: str, end_date: str, interval: str = "month"
    ) -> List[Dict[str, Any]]:
        return PurchaseQueryService.get_purchase_trends(start_date, end_date, interval)

    @staticmethod
    def get_top_suppliers(
        start_date: str, end_date: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        return PurchaseQueryService.get_top_suppliers(start_date, end_date, limit)

    # void_purchase removed (alias for delete_purchase)

    @staticmethod
    def get_supplier_purchases(supplier: str) -> List[Purchase]:
        return PurchaseQueryService.get_supplier_purchases(supplier)

    # update_purchase_reference removed (unimplemented)

    @staticmethod
    def get_purchase_statistics(start_date: str, end_date: str) -> Dict[str, Any]:
        return PurchaseQueryService.get_purchase_statistics(start_date, end_date)

    @staticmethod
    def get_purchase_history(start_date: str, end_date: str) -> List[Purchase]:
        return PurchaseQueryService.get_purchase_history(start_date, end_date)

    @staticmethod
    def clear_cache():
        PurchaseQueryService.clear_cache()
        logger.debug("Purchase cache cleared")
