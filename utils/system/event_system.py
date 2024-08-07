from PySide6.QtCore import QObject, Signal
from typing import Any, Dict, Callable, Optional, List

class EventSystem(QObject):
    """
    A centralized event system for inter-component communication.
    
    This class provides signals that can be emitted when certain events occur
    in the application, allowing different components to react to these events.
    """

    # Product-related signals
    product_added = Signal(int)  # Emits the ID of the added product
    product_updated = Signal(int)  # Emits the ID of the updated product
    product_deleted = Signal(int)  # Emits the ID of the deleted product

    # Purchase-related signals
    purchase_added = Signal(int)  # Emits the ID of the added purchase
    purchase_updated = Signal(int)  # Emits the ID of the updated purchase
    purchase_deleted = Signal(int)  # Emits the ID of the deleted purchase

    # Sale-related signals
    sale_added = Signal(int)  # Emits the ID of the added sale
    sale_updated = Signal(int)  # Emits the ID of the updated sale
    sale_deleted = Signal(int)  # Emits the ID of the deleted sale

    # Inventory-related signals
    inventory_changed = Signal(int)  # Emits the ID of the product whose inventory changed

    # Customer-related signals
    customer_added = Signal(int)  # Emits the ID of the added customer
    customer_updated = Signal(int)  # Emits the ID of the updated customer
    customer_deleted = Signal(int)  # Emits the ID of the deleted customer

    # Category-related signals
    category_added = Signal(int)  # Emits the ID of the added category
    category_updated = Signal(int)  # Emits the ID of the updated category
    category_deleted = Signal(int)  # Emits the ID of the deleted category

    # General application signals
    app_settings_changed = Signal(Dict[str, Any])  # Emits a dictionary of changed settings
    data_import_completed = Signal(bool)  # Emits True if import was successful, False otherwise
    data_export_completed = Signal(bool)  # Emits True if export was successful, False otherwise

    def __init__(self):
        super().__init__()
        self._signal_map = {
            'product_added': self.product_added,
            'product_updated': self.product_updated,
            'product_deleted': self.product_deleted,
            'purchase_added': self.purchase_added,
            'purchase_updated': self.purchase_updated,
            'purchase_deleted': self.purchase_deleted,
            'sale_added': self.sale_added,
            'sale_updated': self.sale_updated,
            'sale_deleted': self.sale_deleted,
            'inventory_changed': self.inventory_changed,
            'customer_added': self.customer_added,
            'customer_updated': self.customer_updated,
            'customer_deleted': self.customer_deleted,
            'category_added': self.category_added,
            'category_updated': self.category_updated,
            'category_deleted': self.category_deleted,
            'app_settings_changed': self.app_settings_changed,
            'data_import_completed': self.data_import_completed,
            'data_export_completed': self.data_export_completed,
        }

    def emit_event(self, event_name: str, *args: Any) -> None:
        """
        Emit an event by name with optional arguments.

        Args:
            event_name (str): The name of the event to emit.
            *args: Variable length argument list to pass with the event.

        Raises:
            ValueError: If the event_name is not recognized.
        """
        if event_name in self._signal_map:
            self._signal_map[event_name].emit(*args)
        else:
            raise ValueError(f"Unknown event: {event_name}")

    def connect_to_event(self, event_name: str, slot: Callable[..., None]) -> None:
        """
        Connect a slot (callback function) to a specific event.

        Args:
            event_name (str): The name of the event to connect to.
            slot (Callable[..., None]): The function to be called when the event is emitted.

        Raises:
            ValueError: If the event_name is not recognized.
        """
        if event_name in self._signal_map:
            self._signal_map[event_name].connect(slot)
        else:
            raise ValueError(f"Unknown event: {event_name}")

    def disconnect_from_event(self, event_name: str, slot: Optional[Callable[..., None]] = None) -> None:
        """
        Disconnect a slot (callback function) from a specific event.

        Args:
            event_name (str): The name of the event to disconnect from.
            slot (Optional[Callable[..., None]]): The function to be disconnected. If None, all connections are removed.

        Raises:
            ValueError: If the event_name is not recognized.
        """
        if event_name in self._signal_map:
            if slot is None:
                self._signal_map[event_name].disconnect()
            else:
                self._signal_map[event_name].disconnect(slot)
        else:
            raise ValueError(f"Unknown event: {event_name}")

    def get_available_events(self) -> List[str]:
        """
        Get a list of all available event names.

        Returns:
            List[str]: A list of all available event names.
        """
        return list(self._signal_map.keys())

# Global instance of the event system
event_system = EventSystem()
