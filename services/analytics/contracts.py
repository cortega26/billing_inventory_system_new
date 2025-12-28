from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type


@dataclass
class MetricResult:
    """Standardized result wrapper for metric execution."""
    data: List[Dict[str, Any]]
    meta: Dict[str, Any]


class Metric(ABC):
    """Abstract base class for all analytics metrics."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the metric."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the metric calculates."""
        pass

    @property
    @abstractmethod
    def output_schema(self) -> Dict[str, Type]:
        """Expected output fields and their types."""
        pass

    @abstractmethod
    def get_query(self, **kwargs) -> str:
        """Returns the SQL query to execute."""
        pass

    @abstractmethod
    def get_parameters(self, **kwargs) -> tuple:
        """Returns the parameters to bind to the query."""
        pass
    
    def validate_params(self, **kwargs) -> None:
        """Optional hook to validate parameters before execution."""
        pass
