import sqlite3
import logging
from typing import Any, Dict, List
from pathlib import Path

from services.analytics.contracts import Metric, MetricResult
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """
    Engine for executing analytics metrics with read-only database access.
    """
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DATABASE_PATH

    def _get_connection(self) -> sqlite3.Connection:
        """
        Establishes a READ-ONLY connection to the SQLite database.
        URI mode is required for read-only access.
        """
        # Ensure path is absolute and uses forward slashes for URI
        abs_path = self.db_path.resolve().as_posix()
        uri = f"file:{abs_path}?mode=ro"
        
        try:
            conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to analytics DB: {e}")
            raise

    def execute_metric(self, metric: Metric, **kwargs) -> MetricResult:
        """
        Executes a defined Metric against the read-only database.
        
        Args:
            metric: The Metric instance to execute.
            **kwargs: Parameters required by the metric (e.g., start_date, end_date).
            
        Returns:
            MetricResult containing the data rows and metadata.
        """
        try:
            metric.validate_params(**kwargs)
            query = metric.get_query(**kwargs)
            params = metric.get_parameters(**kwargs)
            
            logger.info(f"Executing metric: {metric.name}")
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                data = [dict(row) for row in rows]
                
                return MetricResult(
                    data=data,
                    meta={
                        "metric": metric.name,
                        "count": len(data),
                        "params": kwargs
                    }
                )
                
        except Exception as e:
            logger.error(f"Error executing metric {metric.name}: {e}")
            raise
