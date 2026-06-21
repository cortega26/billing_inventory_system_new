from typing import Any, Dict, List

from database.database_manager import DatabaseManager
from models.enums import QUANTITY_PRECISION
from services.audit_service import AuditService
from services.inventory_service import InventoryService
from services.mutation_coordinator import MutationCoordinator
from utils.exceptions import ValidationException
from utils.math.financial_calculator import FinancialCalculator
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.validators import validate_date, validate_integer


class UpdateSaleWorkflow:
    def __init__(self, sale_service):
        self.sale_service = sale_service

    def execute(
        self, sale_id: int, customer_id: int, date: str, items: List[Dict[str, Any]]
    ) -> None:
        """
        Execute the update sale workflow.
        
        Args:
            sale_id: The ID of the sale to update.
            customer_id: The ID of the customer for the sale.
            date: The sale date in YYYY-MM-DD format.
            items: The list of sale items, each with product_id, quantity, and sell_price.
        """
        # 1. Input Validation
        sale_id = validate_integer(sale_id, min_value=1)
        customer_id = validate_integer(customer_id, min_value=1)
        date = validate_date(date)
        self.sale_service._validate_sale_items(items)

        # Require that the sale exists
        self.sale_service._require_sale(sale_id)

        # Get existing items to perform inventory pre-validation
        old_items = self.sale_service.get_sale_items(sale_id)
        self._validate_inventory_for_sale_update(old_items, items)

        # 2. Financial Calculations
        # Note: item["profit"] was calculated during _validate_sale_items
        total_amount = sum(
            FinancialCalculator.calculate_item_total(
                item["quantity"], item["sell_price"]
            )
            for item in items
        )
        total_profit = sum(item["profit"] for item in items)

        # 3. DB Transaction
        with DatabaseManager.transaction():
            # Revert old stock
            InventoryService.apply_batch_updates(
                old_items, multiplier=1.0, emit_events=False
            )
            
            # Update sale record
            self.sale_service._update_sale(sale_id, customer_id, date, total_amount, total_profit)
            
            # Update sale items (deletes old, inserts new)
            self.sale_service._update_sale_items(sale_id, items)
            
            # Apply new stock deduction
            InventoryService.apply_batch_updates(
                items, multiplier=-1.0, emit_events=False
            )
            
            # Log audit trail
            AuditService.log_operation(
                "update_sale",
                "sale",
                sale_id,
                {
                    "customer_id": customer_id,
                    "date": date,
                    "old_item_count": len(old_items),
                    "new_item_count": len(items),
                    "product_ids": self.sale_service._get_product_ids([*old_items, *items]),
                    "total_amount": total_amount,
                    "total_profit": total_profit,
                },
            )

        logger.info(
            "Sale updated", extra={"sale_id": sale_id, "customer_id": customer_id}
        )

        # 4. Post-Commit Invalidation & Signals
        MutationCoordinator.finalize_mutation(
            entity_id=sale_id,
            items=[*old_items, *items],
            signal=event_system.sale_updated,
            service_cache_clear_fn=self.sale_service.clear_cache,
        )

    def _validate_inventory_for_sale_update(
        self, old_items: List[Any], new_items: List[Dict[str, Any]]
    ) -> None:
        """
        Pre-validate stock for sale updates before opening a transaction.
        """
        old_quantities: Dict[int, float] = {}
        for item in old_items:
            product_id = int(getattr(item, "product_id", 0))
            quantity = float(getattr(item, "quantity", 0.0))
            old_quantities[product_id] = old_quantities.get(product_id, 0.0) + quantity

        new_quantities: Dict[int, float] = {}
        for item in new_items:
            product_id = int(item["product_id"])
            quantity = float(item["quantity"])
            new_quantities[product_id] = new_quantities.get(product_id, 0.0) + quantity

        for product_id, required_quantity in new_quantities.items():
            inventory = InventoryService.get_inventory(product_id)
            current_quantity = float(inventory.quantity) if inventory else 0.0
            restored_quantity = current_quantity + old_quantities.get(product_id, 0.0)
            available_after_update = round(
                restored_quantity - required_quantity, QUANTITY_PRECISION
            )

            if available_after_update < 0:
                raise ValidationException(
                    "Insufficient inventory to update sale for product "
                    f"{product_id}. Available after restore: {restored_quantity}, "
                    f"required: {required_quantity}."
                )
