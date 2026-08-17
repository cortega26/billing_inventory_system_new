from datetime import datetime


def parse_datetime_cell(row, key):
    """Parse a nullable ISO-8601 datetime cell, falling back to now when absent."""
    value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    if value:
        return datetime.fromisoformat(value)
    return datetime.now()


def parse_date_cell(row, key):
    """Parse a date cell, accepting 'YYYY-MM-DD' or ISO-8601 forms."""
    value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    if not value:
        return datetime.now()
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return datetime.fromisoformat(value)
