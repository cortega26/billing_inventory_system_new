import logging
import logging.config
import os
from pathlib import Path
import yaml
import sys

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import DEBUG_LEVEL

def setup_logger():
    config_path = Path(__file__).resolve().parent / 'logging_config.yaml'
    
    if os.path.exists(config_path):
        with open(config_path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        # Fallback configuration if YAML file is not found
        logging.basicConfig(level=DEBUG_LEVEL,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            handlers=[
                                logging.StreamHandler(),
                                logging.FileHandler("inventory_system.log")
                            ])

    logger = logging.getLogger('inventory_system')
    
    return logger

logger = setup_logger()

def log_exception(exc_type, exc_value, exc_traceback):
    """
    Log an exception with full traceback.
    """
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# Set the exception hook to use our custom logger
sys.excepthook = log_exception