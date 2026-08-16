from collections.abc import Callable
from typing import Any

from services.analytics_service import AnalyticsService
from services.inventory_service import InventoryService
from utils.helpers import get_product_ids_from_items
from utils.system.event_system import event_system
from utils.system.logger import logger


class MutationCoordinator:
    @staticmethod
    def finalize_mutation(
        entity_id: int,
        items: list[Any],
        signal: Any,
        service_cache_clear_fn: Callable[[], None] | None = None,
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
        product_ids = get_product_ids_from_items(items)
        for product_id in product_ids:
            try:
                event_system.inventory_changed.emit(product_id)
            except Exception as e:
                logger.error(
                    f"Error emitting inventory_changed for product {product_id}: {e}"
                )

        # 4. Emit specific signal
        try:
            signal.emit(entity_id)
        except Exception as e:
            logger.error(f"Error emitting signal {signal}: {e}")
