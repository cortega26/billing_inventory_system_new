import random
import string
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple


def generate_unique_barcode(length: int = 8) -> str:
    """Generate a unique barcode for testing."""
    return "".join(random.choices(string.digits, k=length))


def create_test_product_data(barcode: Optional[str] = None) -> Dict[str, Any]:
    """Create test product data with optional barcode."""
    return {
        "name": f"Test Product {random.randint(1000, 9999)}",
        "description": "Test Description",
        "category_id": 1,
        "cost_price": 1000.0,
        "sell_price": 1500.0,
        "barcode": barcode or generate_unique_barcode(),
    }


def create_test_sale_data(product_id: int) -> Dict[str, Any]:
    """Create test sale data."""
    if not isinstance(product_id, int) or product_id <= 0:
        raise ValueError("product_id must be a positive integer")

    return {
        "customer_id": None,  # Optional customer ID
        "date": date.today().isoformat(),
        "items": [{"product_id": product_id, "quantity": 5, "unit_price": 1500.0}],
    }


def create_test_purchase_data(product_id: int) -> Dict[str, Any]:
    """Create test purchase data."""
    return {
        "supplier": f"Test Supplier {random.randint(1000, 9999)}",
        "date": date.today().isoformat(),
        "items": [{"product_id": product_id, "quantity": 10, "price": 1000.0}],
    }


def create_test_db_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized test database response."""
    return {
        "id": data.get("id", 1),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        **data,
    }


def create_test_date_range(
    days_back: int = 30, future: bool = False
) -> Tuple[str, str]:
    """Create a test date range."""
    today = date.today()
    if future:
        end_date = today + timedelta(days=days_back)
        start_date = today
    else:
        end_date = today
        start_date = today - timedelta(days=days_back)
    return start_date.isoformat(), end_date.isoformat()


def create_test_timestamp() -> str:
    """Create a test timestamp in ISO format."""
    return datetime.now().replace(microsecond=0).isoformat()
