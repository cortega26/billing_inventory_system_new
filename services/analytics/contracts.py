from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from models.enums import SaleStatus
from utils.validation.validators import validate_date


@dataclass
class MetricResult:
    """Standardized result wrapper for metric execution."""

    data: list[dict[str, Any]]
    meta: dict[str, Any]


class Metric(ABC):
    """Abstract base class for all analytics metrics."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the metric."""
        pass

    @abstractmethod
    def get_query(self, **kwargs) -> str:
        """Returns the SQL query to execute."""
        pass

    @abstractmethod
    def get_parameters(self, **kwargs) -> tuple:
        """Returns the parameters to bind to the query."""
        pass

    @abstractmethod
    def validate_params(self, **kwargs) -> None:
        """Optional hook to validate parameters before execution."""
        pass


class DateRangeMetric(Metric):
    """Base for metrics filtered by an inclusive start_date/end_date pair."""

    def validate_params(self, **kwargs) -> None:
        validate_date(kwargs["start_date"])
        validate_date(kwargs["end_date"])

    def get_parameters(self, **kwargs) -> tuple:
        return (
            kwargs["start_date"],
            kwargs["end_date"],
            SaleStatus.CONFIRMED.value,
        )
