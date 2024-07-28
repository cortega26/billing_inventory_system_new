"""Configuration settings for the Inventory and Billing System."""
from pathlib import Path

# Database
DATABASE_NAME = 'billing_inventory.db'
DATABASE_PATH = Path(__file__).parent / DATABASE_NAME

# Application settings
APP_NAME = "Inventory and Billing System"
APP_VERSION = "2.0"
COMPANY_NAME = "El Rincón de Ébano"

# Analytics settings
LOYALTY_THRESHOLD = 5  # Number of purchases to be considered a loyal customer