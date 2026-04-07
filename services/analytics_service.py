from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Tuple

from database.database_manager import DatabaseManager
from services.analytics.engine import AnalyticsEngine
from services.analytics.metrics import (
    DepartmentSalesMetric,
    ProductProfitMetric,
    ProfitMarginDistributionMetric,
    ProfitTrendMetric,
    SalesDailyMetric,
    SalesSummaryMetric,
    TopProductsMetric,
    WeeklyProfitTrendMetric,
    WeekdaySalesMetric,
)
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, ValidationException
from utils.system.logger import logger
from utils.validation.validators import validate_date, validate_integer


class AnalyticsService:
    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_by_weekday(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        metric_result = AnalyticsEngine().execute_metric(
            WeekdaySalesMetric(),
            start_date=start_date,
            end_date=end_date,
        )
        result = [
            {
                "weekday": row["weekday"],
                "total_sales": row["total_sales"],
                "sale_count": row["sale_count"],
            }
            for row in metric_result.data
        ]
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
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        limit = validate_integer(limit, min_value=1, max_value=1000)
        metric_result = AnalyticsEngine().execute_metric(
            TopProductsMetric(),
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        result = [
            {
                "id": row["product_id"],
                "product_id": row["product_id"],
                "name": row["name"],
                "total_quantity": row["total_quantity"],
                "total_revenue": row["total_revenue"],
                "sale_count": row["sale_count"],
            }
            for row in metric_result.data
        ]
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
    def get_sales_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Returns a list of { 'date': 'YYYY-MM-DD', 'daily_sales': sum_of_that_day, 'sale_count': ...}
        ensuring the line chart can parse date with "yyyy-MM-dd" and sums daily totals.
        """
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        metric_result = AnalyticsEngine().execute_metric(
            SalesDailyMetric(),
            start_date=start_date,
            end_date=end_date,
        )
        result = [
            {
                "date": row["date"],
                "daily_sales": row["total_sales"],
                "sale_count": row["sale_count"],
            }
            for row in metric_result.data
        ]
        logger.info(
            "Sales trend retrieved",
            extra={"start_date": start_date, "end_date": end_date},
        )
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_weekly_profit_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        metric_result = AnalyticsEngine().execute_metric(
            WeeklyProfitTrendMetric(),
            start_date=start_date,
            end_date=end_date,
        )
        result = [
            {
                "week": row["week"],
                "week_start": row["week_start"],
                "weekly_profit": row["weekly_profit"],
            }
            for row in metric_result.data
        ]
        logger.info(
            "Weekly profit trend retrieved",
            extra={"start_date": start_date, "end_date": end_date},
        )
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_and_volume_by_product(
        start_date: str, end_date: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        limit = validate_integer(limit, min_value=1, max_value=100)
        metric_result = AnalyticsEngine().execute_metric(
            ProductProfitMetric(),
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        result = [
            {
                "id": row["product_id"],
                "name": row["name"],
                "total_profit": row["total_profit"],
                "sales_volume": row["sales_volume"],
            }
            for row in metric_result.data
        ]
        logger.info(f"Retrieved profit and volume by product: {len(result)} products")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_category_performance(
        start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        metric_result = AnalyticsEngine().execute_metric(
            DepartmentSalesMetric(),
            start_date=start_date,
            end_date=end_date,
        )
        result = [
            {
                "category": row["category"],
                "total_sales": row["total_sales"],
                "number_of_products_sold": row["units_sold"],
                "sale_count": row["sale_count"],
            }
            for row in metric_result.data
        ]
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
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        limit = validate_integer(limit, min_value=1, max_value=1000)
        metric_result = AnalyticsEngine().execute_metric(
            ProductProfitMetric(),
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        result = [
            {
                "id": row["product_id"],
                "product_id": row["product_id"],
                "name": row["name"],
                "total_revenue": row["total_revenue"],
                "total_cost": row["total_cost"],
                "total_profit": row["total_profit"],
                "sale_count": row["sale_count"],
            }
            for row in metric_result.data
        ]
        logger.info(f"Retrieved profit by product: {len(result)} products")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        metric_result = AnalyticsEngine().execute_metric(
            ProfitTrendMetric(),
            start_date=start_date,
            end_date=end_date,
        )
        result = [
            {
                "date": row["date"],
                "daily_revenue": row["daily_revenue"],
                "daily_profit": row["daily_profit"],
                "sale_count": row["sale_count"],
            }
            for row in metric_result.data
        ]
        logger.info(f"Retrieved profit trend: {len(result)} days")
        return result

    @staticmethod
    @lru_cache(maxsize=32)
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_profit_margin_distribution(
        start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        metric_result = AnalyticsEngine().execute_metric(
            ProfitMarginDistributionMetric(),
            start_date=start_date,
            end_date=end_date,
        )
        result = [
            {
                "margin_range": row["margin_range"],
                "product_count": row["product_count"],
                "average_margin": row["average_margin"],
                "total_sales": row["total_sales"],
            }
            for row in metric_result.data
        ]
        logger.info(f"Retrieved profit margin distribution: {len(result)} ranges")
        return result

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def get_sales_summary(start_date: str, end_date: str) -> Dict[str, Any]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        AnalyticsService._validate_date_range(start_date, end_date)
        metric_result = AnalyticsEngine().execute_metric(
            SalesSummaryMetric(),
            start_date=start_date,
            end_date=end_date,
        )
        if not metric_result.data:
            logger.warning(f"No sales data found for period {start_date} to {end_date}")
            return {
                "total_sales": 0,
                "total_revenue": 0,
                "total_profit": 0,
                "average_sale_value": 0,
                "unique_customers": 0,
            }
        result = metric_result.data[0]
        logger.info(f"Retrieved sales summary from {start_date} to {end_date}")
        return {
            "total_sales": result["total_sales"],
            "total_revenue": result["total_revenue"],
            "total_profit": result["total_profit"],
            "average_sale_value": result["average_sale_value"],
            "unique_customers": result["unique_customers"],
        }

    @staticmethod
    def clear_cache():
        AnalyticsService.get_sales_by_weekday.cache_clear()
        AnalyticsService.get_top_selling_products.cache_clear()
        AnalyticsService.get_sales_trend.cache_clear()
        AnalyticsService.get_weekly_profit_trend.cache_clear()
        AnalyticsService.get_profit_and_volume_by_product.cache_clear()
        AnalyticsService.get_category_performance.cache_clear()
        AnalyticsService.get_profit_by_product.cache_clear()
        AnalyticsService.get_profit_trend.cache_clear()
        AnalyticsService.get_profit_margin_distribution.cache_clear()
        logger.debug("Analytics cache cleared")

    @staticmethod
    def get_date_range(range_type: str) -> Tuple[str, str]:
        today = datetime.now().date()
        date_ranges = {
            "today": (today, today),
            "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
            "this_week": (today - timedelta(days=today.weekday()), today),
            "this_month": (today.replace(day=1), today),
            "this_year": (today.replace(month=1, day=1), today),
        }

        if range_type in date_ranges:
            start_date, end_date = date_ranges[range_type]
            logger.debug(f"Date range for {range_type}: {start_date} to {end_date}")
            return start_date.isoformat(), end_date.isoformat()
        else:
            logger.error(f"Invalid range type: {range_type}")
            raise ValueError("Invalid range type")

    @staticmethod
    def _validate_date_range(start_date: str, end_date: str) -> None:
        """Validate date range for analytics queries."""
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            today = datetime.now()

            if start > today or end > today:
                raise ValidationException("Date range cannot be in the future")
            if start > end:
                raise ValidationException("Start date must be before end date")

        except ValueError as e:
            raise ValidationException(f"Invalid date format: {str(e)}")
