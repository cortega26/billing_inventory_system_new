from services.analytics.contracts import Metric, MetricResult
from services.analytics.engine import AnalyticsEngine
from services.analytics.metrics import (
    DepartmentSalesMetric,
    InventoryAgingMetric,
    LowStockMetric,
    ProductProfitMetric,
    ProfitTrendMetric,
    ProfitMarginDistributionMetric,
    SalesDailyMetric,
    SalesSummaryMetric,
    TopProductsMetric,
    WeeklyProfitTrendMetric,
    WeekdaySalesMetric,
)

__all__ = [
    "AnalyticsEngine",
    "Metric",
    "MetricResult",
    "SalesDailyMetric",
    "WeekdaySalesMetric",
    "TopProductsMetric",
    "LowStockMetric",
    "InventoryAgingMetric",
    "DepartmentSalesMetric",
    "ProfitTrendMetric",
    "WeeklyProfitTrendMetric",
    "ProductProfitMetric",
    "ProfitMarginDistributionMetric",
    "SalesSummaryMetric",
]
