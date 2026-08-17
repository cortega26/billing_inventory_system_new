from typing import Any

from database.database_manager import DatabaseManager
from models.enums import (
    MAX_PRICE_CLP,
    MAX_PURCHASE_ITEMS,
    QUANTITY_PRECISION,
)
from models.purchase import Purchase
from services.audit_service import AuditService
from services.inventory_service import InventoryService
from services.mutation_coordinator import MutationCoordinator
from services.purchase_query_service import PurchaseQueryService
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
    def get_purchase(purchase_id: int) -> Purchase | None:
        return PurchaseQueryService.get_purchase(purchase_id)

    @staticmethod
    def _require_purchase(purchase_id: int) -> Purchase:
        purchase = PurchaseService.get_purchase(purchase_id)
        if purchase is not None:
            return purchase

        raise NotFoundException(f"Purchase with ID {purchase_id} not found")

    @staticmethod
    def get_all_purchases() -> list[Purchase]:
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
    def get_suppliers() -> list[str]:
        return PurchaseQueryService.get_suppliers()

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
    def get_purchases_by_supplier(
        supplier: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        return PurchaseQueryService.get_purchases_by_supplier(
            supplier, start_date, end_date
        )

    @staticmethod
    def get_purchase_trends(
        start_date: str, end_date: str, interval: str = "month"
    ) -> list[dict[str, Any]]:
        return PurchaseQueryService.get_purchase_trends(start_date, end_date, interval)

    @staticmethod
    def get_top_suppliers(
        start_date: str, end_date: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        return PurchaseQueryService.get_top_suppliers(start_date, end_date, limit)

    # void_purchase removed (alias for delete_purchase)

    @staticmethod
    def get_supplier_purchases(supplier: str) -> list[Purchase]:
        return PurchaseQueryService.get_supplier_purchases(supplier)

    # update_purchase_reference removed (unimplemented)

    @staticmethod
    def get_purchase_statistics(start_date: str, end_date: str) -> dict[str, Any]:
        return PurchaseQueryService.get_purchase_statistics(start_date, end_date)

    @staticmethod
    def get_purchase_history(start_date: str, end_date: str) -> list[Purchase]:
        return PurchaseQueryService.get_purchase_history(start_date, end_date)

    @classmethod
    def clear_cache(cls) -> None:
        PurchaseQueryService.clear_cache()
        logger.debug("Purchase cache cleared")
