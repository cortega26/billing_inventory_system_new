import os
from typing import Any

from utils.system.logger import logger

try:
    if os.environ.get("USE_MOCK_EVENT_SYSTEM"):
        raise ImportError("Forcing MockEventSystem for tests")
    from PySide6.QtCore import QObject, Signal  # pyright: ignore[reportAssignmentType]
except ImportError:
    # Fallback for headless environments/tests
    logger.warning("PySide6 not found or disabled, using MockEventSystem")

    class QObject:
        pass

    class MockSignal:
        def __init__(self, *args):
            self._slots = []

        def emit(self, *args):
            logger.debug(f"MockSignal emitted: {args}")
            for slot in self._slots:
                try:
                    slot(*args)
                except Exception as e:
                    # Signal emission propagates exceptions in direct connection mode
                    raise e

        def connect(self, slot):
            logger.debug(f"MockSignal connected: {slot}")
            self._slots.append(slot)

        def disconnect(self, slot=None):
            logger.debug(f"MockSignal disconnected: {slot}")
            if slot:
                if slot in self._slots:
                    self._slots.remove(slot)
            else:
                self._slots.clear()

    Signal = MockSignal


class EventSystem(QObject):
    """
    A centralized event system for inter-component communication.

    This class provides signals that can be emitted when certain events occur
    in the application, allowing different components to react to these events.
    """

    # Product-related signals
    product_added: Any = Signal(
        object
    )  # Emits the ID of the added product or data dict
    product_updated: Any = Signal(
        object
    )  # Emits the ID of the updated product or data dict
    product_deleted: Any = Signal(object)  # Emits the ID of the deleted product

    # Purchase-related signals
    purchase_added: Any = Signal(object)  # Emits the ID of the added purchase
    purchase_updated: Any = Signal(object)  # Emits the ID of the updated purchase
    purchase_deleted: Any = Signal(object)  # Emits the ID of the deleted purchase

    # Sale-related signals
    sale_added: Any = Signal(object)  # Emits the ID of the added sale
    sale_updated: Any = Signal(object)  # Emits the ID of the updated sale
    sale_deleted: Any = Signal(object)  # Emits the ID of the deleted sale

    # Inventory-related signals
    inventory_changed: Any = Signal(
        object
    )  # Emits the ID of the product whose inventory changed

    # Customer-related signals
    customer_added: Any = Signal(object)  # Emits the ID of the added customer
    customer_updated: Any = Signal(object)  # Emits the ID of the updated customer
    customer_deleted: Any = Signal(object)  # Emits the ID of the deleted customer

    # Category-related signals
    category_added: Any = Signal(object)  # Emits the ID of the added category
    category_updated: Any = Signal(object)  # Emits the ID of the updated category
    category_deleted: Any = Signal(object)  # Emits the ID of the deleted category

    # Backup signals
    backup_skipped: Any = Signal(
        dict
    )  # Emits metadata when automatic backup is skipped
    backup_completed: Any = Signal(object)  # Emits backup path or metadata on success

    def __init__(self):
        super().__init__()

    def clear_all_connections(self) -> None:
        """
        Clear all event connections.
        """
        for name in ALL_SIGNALS:
            getattr(self, name).disconnect()
        logger.info("All event connections cleared")


# Global instance of the event system
event_system = EventSystem()

# Every signal exposed by EventSystem, used to clear connections
ALL_SIGNALS = (
    "product_added",
    "product_updated",
    "product_deleted",
    "purchase_added",
    "purchase_updated",
    "purchase_deleted",
    "sale_added",
    "sale_updated",
    "sale_deleted",
    "inventory_changed",
    "customer_added",
    "customer_updated",
    "customer_deleted",
    "category_added",
    "category_updated",
    "category_deleted",
    "backup_skipped",
    "backup_completed",
)
