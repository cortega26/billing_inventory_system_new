from PySide6.QtCore import QObject, Signal

class EventSystem(QObject):
    product_added = Signal()
    purchase_added = Signal()
    sale_added = Signal()

event_system = EventSystem()