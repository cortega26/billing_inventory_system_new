from PySide6.QtCore import QObject, Signal
from typing import Any

class EventSystem(QObject):
    """
    A simple event system for inter-component communication.
    
    This class provides signals that can be emitted when certain events occur
    in the application, allowing different components to react to these events.
    """

    product_added = Signal(int)  # Emits the ID of the added product
    product_updated = Signal(int)  # Emits the ID of the updated product
    product_deleted = Signal(int)  # Emits the ID of the deleted product

    purchase_added = Signal(int)  # Emits the ID of the added purchase
    purchase_updated = Signal(int)  # Emits the ID of the updated purchase
    purchase_deleted = Signal(int)  # Emits the ID of the deleted purchase

    sale_added = Signal(int)  # Emits the ID of the added sale
    sale_updated = Signal(int)  # Emits the ID of the updated sale
    sale_deleted = Signal(int)  # Emits the ID of the deleted sale

    inventory_changed = Signal(int)  # Emits the ID of the product whose inventory changed

    customer_added = Signal(int)  # Emits the ID of the added customer
    customer_updated = Signal(int)  # Emits the ID of the updated customer
    customer_deleted = Signal(int)  # Emits the ID of the deleted customer

    def emit_event(self, event_name: str, *args: Any) -> None:
        """
        Emit an event by name with optional arguments.

        Args:
            event_name (str): The name of the event to emit.
            *args: Variable length argument list to pass with the event.
        """
        if hasattr(self, event_name):
            signal = getattr(self, event_name)
            signal.emit(*args)
        else:
            raise ValueError(f"Unknown event: {event_name}")

# Global instance of the event system
event_system = EventSystem()