from functools import lru_cache
from typing import Any

from services.analytics.contracts import Metric
from services.analytics.engine import AnalyticsEngine
from services.analytics.metrics import (
    DepartmentSalesMetric,
    InventoryAgingMetric,
    LowStockMetric,
    ProductProfitMetric,
    ProfitMarginDistributionMetric,
    ProfitTrendMetric,
    SalesDailyMetric,
    SalesSummaryMetric,
    TopProductsMetric,
    WeekdaySalesMetric,
    WeeklyProfitTrendMetric,
)
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, ValidationException
from utils.system.logger import logger
from utils.validation.validators import (
    validate_float_non_negative,
    validate_integer,
)


class AnalyticsService:
    @staticmethod
    def _execute_metric(metric: Metric, row_mapper, **kwargs) -> list:
        result = AnalyticsEngine().execute_metric(metric, **kwargs)
        return [row_mapper(row) for row in result.data]

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_by_weekday(start_date: str, end_date: str) -> list[dict[str, Any]]:
        result = AnalyticsService._execute_metric(
            WeekdaySalesMetric(),
            lambda row: {
                "weekday": row["weekday"],
                "total_sales": row["total_sales"],
                "sale_count": row["sale_count"],
            },
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            "Sales by weekday retrieved",
            extra={"start_date": start_date, "end_date": end_date},
        )
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_top_selling_products(
        start_date: str, end_date: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        limit = validate_integer(limit, min_value=1, max_value=1000)
        result = AnalyticsService._execute_metric(
            TopProductsMetric(),
            lambda row: {
                "id": row["product_id"],
                "product_id": row["product_id"],
                "name": row["name"],
                "total_quantity": row["total_quantity"],
                "total_revenue": row["total_revenue"],
                "sale_count": row["sale_count"],
            },
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        logger.info(
            "Top selling products retrieved",
            extra={"start_date": start_date, "end_date": end_date, "limit": limit},
        )
        return result

    ###########################################################################
    # FIX 1: Summation & date truncation for daily-based "Sales Trend"
    ###########################################################################
    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_trend(start_date: str, end_date: str) -> list[dict[str, Any]]:
        """
        Returns a list of { 'date': 'YYYY-MM-DD', 'daily_sales': sum_of_that_day, 'sale_count': ...}
        ensuring the line chart can parse date with "yyyy-MM-dd" and sums daily totals.
        """
        result = AnalyticsService._execute_metric(
            SalesDailyMetric(),
            lambda row: {
                "date": row["date"],
                "daily_sales": row["total_sales"],
                "sale_count": row["sale_count"],
            },
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            "Sales trend retrieved",
            extra={"start_date": start_date, "end_date": end_date},
        )
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_weekly_profit_trend(start_date: str, end_date: str) -> list[dict[str, Any]]:
        result = AnalyticsService._execute_metric(
            WeeklyProfitTrendMetric(),
            lambda row: {
                "week": row["week"],
                "week_start": row["week_start"],
                "weekly_profit": row["weekly_profit"],
            },
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            "Weekly profit trend retrieved",
            extra={"start_date": start_date, "end_date": end_date},
        )
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_category_performance(
        start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        result = AnalyticsService._execute_metric(
            DepartmentSalesMetric(),
            lambda row: {
                "category": row["category"],
                "total_sales": row["total_sales"],
                "number_of_products_sold": row["units_sold"],
                "sale_count": row["sale_count"],
            },
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            "Category performance retrieved",
            extra={"start_date": start_date, "end_date": end_date},
        )
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_by_product(
        start_date: str, end_date: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        limit = validate_integer(limit, min_value=1, max_value=1000)
        result = AnalyticsService._execute_metric(
            ProductProfitMetric(),
            lambda row: {
                "id": row["product_id"],
                "product_id": row["product_id"],
                "name": row["name"],
                "total_revenue": row["total_revenue"],
                "total_cost": row["total_cost"],
                "total_profit": row["total_profit"],
                "sale_count": row["sale_count"],
            },
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        logger.info(f"Retrieved profit by product: {len(result)} products")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_trend(start_date: str, end_date: str) -> list[dict[str, Any]]:
        result = AnalyticsService._execute_metric(
            ProfitTrendMetric(),
            lambda row: {
                "date": row["date"],
                "daily_revenue": row["daily_revenue"],
                "daily_profit": row["daily_profit"],
                "sale_count": row["sale_count"],
            },
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(f"Retrieved profit trend: {len(result)} days")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_margin_distribution(
        start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        result = AnalyticsService._execute_metric(
            ProfitMarginDistributionMetric(),
            lambda row: {
                "margin_range": row["margin_range"],
                "product_count": row["product_count"],
                "average_margin": row["average_margin"],
                "total_sales": row["total_sales"],
            },
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(f"Retrieved profit margin distribution: {len(result)} ranges")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_low_stock(threshold: float = 10) -> list[dict[str, Any]]:
        threshold = validate_float_non_negative(threshold)
        result = AnalyticsService._execute_metric(
            LowStockMetric(),
            lambda row: {
                "id": row["product_id"],
                "name": row["name"],
                "quantity": row["quantity"],
            },
            threshold=threshold,
        )
        logger.info(f"Retrieved low stock products: {len(result)}")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_inventory_aging(days: int = 30) -> list[dict[str, Any]]:
        days = validate_integer(days, min_value=0)
        result = AnalyticsService._execute_metric(
            InventoryAgingMetric(),
            lambda row: {
                "id": row["product_id"],
                "name": row["name"],
                "stock_quantity": row["stock_quantity"],
                "last_sold_date": row["last_sold_date"],
            },
            days=days,
        )
        logger.info(f"Retrieved inventory aging: {len(result)} products")
        return result

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_summary(start_date: str, end_date: str) -> dict[str, Any]:
        result = AnalyticsService._execute_metric(
            SalesSummaryMetric(),
            lambda row: {
                "total_sales": row["total_sales"],
                "total_revenue": row["total_revenue"],
                "total_profit": row["total_profit"],
                "average_sale_value": row["average_sale_value"],
                "unique_customers": row["unique_customers"],
            },
            start_date=start_date,
            end_date=end_date,
        )
        if not result:
            logger.warning(f"No sales data found for period {start_date} to {end_date}")
            return {
                "total_sales": 0,
                "total_revenue": 0,
                "total_profit": 0,
                "average_sale_value": 0,
                "unique_customers": 0,
            }
        summary = result[0]
        logger.info(f"Retrieved sales summary from {start_date} to {end_date}")
        return summary

    @classmethod
    def clear_cache(cls) -> None:
        AnalyticsService.get_sales_by_weekday.cache_clear()
        AnalyticsService.get_top_selling_products.cache_clear()
        AnalyticsService.get_sales_trend.cache_clear()
        AnalyticsService.get_weekly_profit_trend.cache_clear()
        AnalyticsService.get_category_performance.cache_clear()
        AnalyticsService.get_profit_by_product.cache_clear()
        AnalyticsService.get_profit_trend.cache_clear()
        AnalyticsService.get_profit_margin_distribution.cache_clear()
        AnalyticsService.get_low_stock.cache_clear()
        AnalyticsService.get_inventory_aging.cache_clear()
        logger.debug("Analytics cache cleared")
