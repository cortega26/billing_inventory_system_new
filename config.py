"""Configuration settings for the Inventory and Billing System."""
from pathlib import Path
import logging

# Database
DATABASE_NAME = 'billing_inventory.db'
DATABASE_PATH = Path(__file__).parent / DATABASE_NAME

# Application settings
APP_NAME = "Inventory and Billing System"
APP_VERSION = "2.0"
COMPANY_NAME = "El Rincón de Ébano"

# Analytics settings
LOYALTY_THRESHOLD = 5  # Number of purchases to be considered a loyal customer

# Debug Level
DEBUG_LEVELS = {
    1: logging.CRITICAL,
    2: logging.ERROR,
    3: logging.WARNING,
    4: logging.INFO,
    5: logging.DEBUG
}

# Set the desired debug level by changing this number
DEBUG_LEVEL = DEBUG_LEVELS[4]  # Change this number to set the debug level
