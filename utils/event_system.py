from PySide6.QtCore import QObject, Signal

class EventSystem(QObject):
    """
    A simple event system for inter-component communication.
    
    This class provides signals that can be emitted when certain events occur
    in the application, allowing different components to react to these events.
    """

    product_added = Signal()
    purchase_added = Signal()
    sale_added = Signal()

# Global instance of the event system
event_system = EventSystem()