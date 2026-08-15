from enum import StrEnum


class StockMovementType(StrEnum):
    SALE = "sale"
    PURCHASE = "purchase"
    ADJUSTMENT = "adjustment"


class InventoryAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    SET = "set"


class TimeInterval(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


# Constants
QUANTITY_PRECISION = 3
MAX_PRICE_CLP = 1_000_000
MAX_SALE_ITEMS = 1000
MAX_PURCHASE_ITEMS = 1000
