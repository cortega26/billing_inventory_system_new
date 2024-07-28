import logging
import sys
from pathlib import Path

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import DEBUG_LEVEL

def setup_logger():
    logger = logging.getLogger('inventory_system')
    logger.setLevel(DEBUG_LEVEL)
    
    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(DEBUG_LEVEL)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Add formatter to ch
    ch.setFormatter(formatter)
    
    # Add ch to logger
    logger.addHandler(ch)
    
    return logger

logger = setup_logger()
