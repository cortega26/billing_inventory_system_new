from enum import Enum, auto

class StockMovementType(str, Enum):
    SALE = "sale"
    PURCHASE = "purchase"
    ADJUSTMENT = "adjustment"

class InventoryAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    SET = "set"

class TimeInterval(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

# Constants
QUANTITY_PRECISION = 3
MAX_PRICE_CLP = 1_000_000
MAX_SALE_ITEMS = 1000
MAX_PURCHASE_ITEMS = 1000
EDIT_WINDOW_HOURS = 1240
