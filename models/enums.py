from enum import StrEnum


class InventoryAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"


class TimeInterval(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class SaleStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


# Constants
QUANTITY_PRECISION = 3
MAX_PRICE_CLP = 1_000_000
MAX_SALE_ITEMS = 1000
MAX_PURCHASE_ITEMS = 1000
