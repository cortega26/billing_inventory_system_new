"""Configuration settings for the Inventory and Billing System."""
from pathlib import Path
import logging
import os
from enum import IntEnum
from typing import Dict

# Database
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'billing_inventory.db')
DATABASE_PATH = Path(__file__).parent / DATABASE_NAME

# Application settings
APP_NAME: str = "Inventory and Billing System"
APP_VERSION: str = "2.0"
COMPANY_NAME: str = "El Rincón de Ébano"

# Analytics settings
LOYALTY_THRESHOLD: int = 5  # Number of purchases to be considered a loyal customer

# Debug Level
class DebugLevel(IntEnum):
    CRITICAL = 1
    ERROR = 2
    WARNING = 3
    INFO = 4
    DEBUG = 5

DEBUG_LEVELS: Dict[DebugLevel, int] = {
    DebugLevel.CRITICAL: logging.CRITICAL,
    DebugLevel.ERROR: logging.ERROR,
    DebugLevel.WARNING: logging.WARNING,
    DebugLevel.INFO: logging.INFO,
    DebugLevel.DEBUG: logging.DEBUG
}

# Set the desired debug level by changing this number
DEBUG_LEVEL: int = DEBUG_LEVELS[DebugLevel.INFO]  # Change this to set the debug level