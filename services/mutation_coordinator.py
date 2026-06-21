from typing import Any, Callable, List, Optional

from services.analytics_service import AnalyticsService
from services.inventory_service import InventoryService
from utils.system.event_system import event_system
from utils.system.logger import logger


class MutationCoordinator:
    @staticmethod
    def finalize_mutation(
        entity_id: int,
        items: List[Any],
        signal: Any,
        service_cache_clear_fn: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Unified post-commit finalization for data mutations (sales, purchases, adjustments).
        Clears relevant caches and emits domain events in a consistent sequence.
        """
        # 1. Clear core caches
        InventoryService.clear_cache()
        AnalyticsService.clear_cache()

        # 2. Clear specific service caches if provided
        if service_cache_clear_fn:
            try:
                service_cache_clear_fn()
            except Exception as e:
                logger.error(f"Error clearing service cache: {e}")

        # 3. Emit inventory changed events for affected products
        product_ids = MutationCoordinator._get_product_ids(items)
        for product_id in product_ids:
            try:
                event_system.inventory_changed.emit(product_id)
            except Exception as e:
                logger.error(f"Error emitting inventory_changed for product {product_id}: {e}")

        # 4. Emit specific signal
        try:
            signal.emit(entity_id)
        except Exception as e:
            logger.error(f"Error emitting signal {signal}: {e}")

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
