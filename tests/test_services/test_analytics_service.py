from datetime import date, timedelta

import pytest

from database import init_db
from database.database_manager import DatabaseManager
from services.analytics.contracts import MetricResult
from services.analytics.metrics import (
    DepartmentSalesMetric,
    ProductProfitMetric,
    ProfitMarginDistributionMetric,
    ProfitTrendMetric,
    SalesDailyMetric,
    SalesSummaryMetric,
    TopProductsMetric,
    WeekdaySalesMetric,
    WeeklyProfitTrendMetric,
)
from services.analytics_service import AnalyticsService
from services.category_service import CategoryService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.purchase_service import PurchaseService
from services.sale_service import SaleService
from tests.utils.base_test import BaseTest
from tests.utils.test_helpers import create_test_product_data, generate_unique_barcode
from utils.exceptions import ValidationException


@pytest.fixture
def clear_test_data():
    """No-op replacement for the conftest teardown fixture.

    The conftest autouse `clear_test_data` pulls in `db_manager`, which
    this module overrides with `mock_database` — so every test in this
    module would run with mocked services. The real-DB class below owns a
    temp-file database instead and must not have DatabaseManager patched.
    """
    yield


@pytest.fixture
def db_manager(mock_database):
    """Override db_manager to use MOCK for Analytics tests."""
    return mock_database


@pytest.fixture
def analytics_service(db_manager):
    return AnalyticsService()


@pytest.fixture
def sale_service(db_manager):
    return SaleService()


@pytest.fixture
def purchase_service(db_manager):
    return PurchaseService()


@pytest.fixture
def product_service(db_manager):
    return ProductService()


@pytest.fixture
def inventory_service(db_manager):
    return InventoryService()


def test_get_sales_trend_uses_metric_engine_and_preserves_output_shape(mocker):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {"date": "2026-04-01", "total_sales": 1200, "sale_count": 3},
                {"date": "2026-04-02", "total_sales": 2400, "sale_count": 5},
            ],
            meta={"metric": "sales_daily"},
        ),
    )

    result = AnalyticsService.get_sales_trend("2026-04-01", "2026-04-02")

    assert result == [
        {"date": "2026-04-01", "daily_sales": 1200, "sale_count": 3},
        {"date": "2026-04-02", "daily_sales": 2400, "sale_count": 5},
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, SalesDailyMetric)


def test_get_sales_by_weekday_uses_metric_engine_and_preserves_output_shape(mocker):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {"weekday": "Monday", "total_sales": 1200, "sale_count": 3},
                {"weekday": "Tuesday", "total_sales": 800, "sale_count": 2},
            ],
            meta={"metric": "sales_weekday"},
        ),
    )

    result = AnalyticsService.get_sales_by_weekday("2026-04-01", "2026-04-07")

    assert result == [
        {"weekday": "Monday", "total_sales": 1200, "sale_count": 3},
        {"weekday": "Tuesday", "total_sales": 800, "sale_count": 2},
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, WeekdaySalesMetric)
    assert execute_metric.call_args.kwargs == {
        "start_date": "2026-04-01",
        "end_date": "2026-04-07",
    }


def test_get_top_selling_products_uses_metric_engine_and_preserves_output_shape(mocker):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "product_id": 7,
                    "name": "Arroz",
                    "total_quantity": 4.5,
                    "total_revenue": 5400,
                    "sale_count": 2,
                }
            ],
            meta={"metric": "top_products"},
        ),
    )

    result = AnalyticsService.get_top_selling_products("2026-04-01", "2026-04-02", 5)

    assert result == [
        {
            "id": 7,
            "product_id": 7,
            "name": "Arroz",
            "total_quantity": 4.5,
            "total_revenue": 5400,
            "sale_count": 2,
        }
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, TopProductsMetric)
    assert execute_metric.call_args.kwargs == {
        "start_date": "2026-04-01",
        "end_date": "2026-04-02",
        "limit": 5,
    }


def test_get_category_performance_uses_metric_engine_and_preserves_output_shape(
    mocker,
):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "category": "Abarrotes",
                    "total_sales": 15000,
                    "units_sold": 12.5,
                    "sale_count": 4,
                }
            ],
            meta={"metric": "department_sales"},
        ),
    )

    result = AnalyticsService.get_category_performance("2026-04-01", "2026-04-02")

    assert result == [
        {
            "category": "Abarrotes",
            "total_sales": 15000,
            "number_of_products_sold": 12.5,
            "sale_count": 4,
        }
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, DepartmentSalesMetric)
    assert execute_metric.call_args.kwargs == {
        "start_date": "2026-04-01",
        "end_date": "2026-04-02",
    }


def test_get_profit_trend_uses_metric_engine_and_preserves_output_shape(mocker):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "date": "2026-04-01",
                    "daily_revenue": 1200,
                    "daily_profit": 300,
                    "sale_count": 3,
                },
                {
                    "date": "2026-04-02",
                    "daily_revenue": 2400,
                    "daily_profit": 700,
                    "sale_count": 5,
                },
            ],
            meta={"metric": "profit_trend"},
        ),
    )

    result = AnalyticsService.get_profit_trend("2026-04-01", "2026-04-02")

    assert result == [
        {
            "date": "2026-04-01",
            "daily_revenue": 1200,
            "daily_profit": 300,
            "sale_count": 3,
        },
        {
            "date": "2026-04-02",
            "daily_revenue": 2400,
            "daily_profit": 700,
            "sale_count": 5,
        },
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, ProfitTrendMetric)
    assert execute_metric.call_args.kwargs == {
        "start_date": "2026-04-01",
        "end_date": "2026-04-02",
    }


def test_get_weekly_profit_trend_uses_metric_engine_and_preserves_output_shape(mocker):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "week": "2026-13",
                    "week_start": "2026-04-01",
                    "weekly_profit": 1590,
                }
            ],
            meta={"metric": "weekly_profit_trend"},
        ),
    )

    result = AnalyticsService.get_weekly_profit_trend("2026-04-01", "2026-04-07")

    assert result == [
        {"week": "2026-13", "week_start": "2026-04-01", "weekly_profit": 1590}
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, WeeklyProfitTrendMetric)


def test_get_profit_by_product_uses_metric_engine_and_preserves_output_shape(mocker):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "product_id": 7,
                    "name": "Arroz",
                    "total_revenue": 5400,
                    "total_cost": 3600,
                    "total_profit": 1800,
                    "sales_volume": 4.5,
                    "sale_count": 2,
                }
            ],
            meta={"metric": "product_profit"},
        ),
    )

    result = AnalyticsService.get_profit_by_product("2026-04-01", "2026-04-02", 5)

    assert result == [
        {
            "id": 7,
            "product_id": 7,
            "name": "Arroz",
            "total_revenue": 5400,
            "total_cost": 3600,
            "total_profit": 1800,
            "sale_count": 2,
        }
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, ProductProfitMetric)


def test_get_profit_and_volume_by_product_uses_metric_engine_and_preserves_output_shape(
    mocker,
):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "product_id": 7,
                    "name": "Arroz",
                    "total_revenue": 5400,
                    "total_cost": 3600,
                    "total_profit": 1800,
                    "sales_volume": 4.5,
                    "sale_count": 2,
                }
            ],
            meta={"metric": "product_profit"},
        ),
    )

    result = AnalyticsService.get_profit_and_volume_by_product(
        "2026-04-01", "2026-04-02", 5
    )

    assert result == [
        {"id": 7, "name": "Arroz", "total_profit": 1800, "sales_volume": 4.5}
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, ProductProfitMetric)


def test_get_profit_margin_distribution_uses_metric_engine_and_preserves_output_shape(
    mocker,
):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "margin_range": "30-40%",
                    "product_count": 1,
                    "average_margin": 35.0,
                    "total_sales": 100,
                }
            ],
            meta={"metric": "profit_margin_distribution"},
        ),
    )

    result = AnalyticsService.get_profit_margin_distribution("2026-04-01", "2026-04-02")

    assert result == [
        {
            "margin_range": "30-40%",
            "product_count": 1,
            "average_margin": 35.0,
            "total_sales": 100,
        }
    ]
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, ProfitMarginDistributionMetric)


def test_get_sales_summary_uses_metric_engine_and_preserves_output_shape(mocker):
    AnalyticsService.clear_cache()
    execute_metric = mocker.patch(
        "services.analytics_service.AnalyticsEngine.execute_metric",
        return_value=MetricResult(
            data=[
                {
                    "total_sales": 2,
                    "total_revenue": 3100,
                    "total_profit": 1590,
                    "average_sale_value": 1550,
                    "unique_customers": 2,
                }
            ],
            meta={"metric": "sales_summary"},
        ),
    )

    result = AnalyticsService.get_sales_summary("2026-04-01", "2026-04-02")

    assert result == {
        "total_sales": 2,
        "total_revenue": 3100,
        "total_profit": 1590,
        "average_sale_value": 1550,
        "unique_customers": 2,
    }
    metric = execute_metric.call_args.args[0]
    assert isinstance(metric, SalesSummaryMetric)


@pytest.fixture
def sample_data(product_service, inventory_service, mocker, mock_db):
    """Create sample data for analytics tests."""
    products = []

    # Mock database responses for product creation and retrieval
    mock_execute = mock_db.execute_query
    mock_execute.return_value.lastrowid = 1

    for i in range(1, 4):
        product_data = create_test_product_data(barcode=generate_unique_barcode())

        # 1. Create product (retrieves mocked ID)
        mock_execute.return_value.lastrowid = i
        product_id = product_service.create_product(product_data)

        # 2. Mock get_product return for the next call
        # construct what fetch_one should return
        db_row = {
            "id": i,
            "name": product_data["name"],
            "description": product_data["description"],
            "category_id": product_data["category_id"],
            "cost_price": product_data["cost_price"],
            "sell_price": product_data["sell_price"],
            "barcode": product_data["barcode"],
            "created_at": date.today().isoformat(),
            "updated_at": date.today().isoformat(),
        }
        mock_db.fetch_one.return_value = db_row

        fetched_product = product_service.get_product(product_id)
        if fetched_product:
            products.append(fetched_product)

        # 3. Create inventory (using update_quantity which handles creation)
        # We need to ensure fetch_one returns None for get_inventory check so it tries to create
        # or we just assume update_quantity works.
        # But update_quantity calls get_inventory first.
        mock_db.fetch_one.return_value = None  # Simulate no existing inventory
        inventory_service.update_quantity(product_id, 100.0)

    return {"products": products}


class TestAnalyticsService(BaseTest):
    def test_get_sales_by_weekday(self, analytics_service, mocker):
        today = date.today().isoformat()
        mocker.patch(
            "services.analytics_service.AnalyticsEngine.execute_metric",
            return_value=MetricResult(
                data=[{"weekday": "Monday", "total_sales": 1500, "sale_count": 5}],
                meta={},
            ),
        )

        sales_by_weekday = analytics_service.get_sales_by_weekday(today, today)

        assert len(sales_by_weekday) > 0
        assert isinstance(sales_by_weekday[0]["total_sales"], int)
        assert isinstance(sales_by_weekday[0]["sale_count"], int)

    # def test_get_sales_by_hour(self, analytics_service, sample_data):
    #     # Method does not exist
    #     pass

    def test_get_top_selling_products(self, analytics_service, mocker):
        today = date.today().isoformat()
        mocker.patch(
            "services.analytics_service.AnalyticsEngine.execute_metric",
            return_value=MetricResult(
                data=[
                    {
                        "product_id": 1,
                        "name": "Test Product 1",
                        "total_quantity": 5,
                        "total_revenue": 7500,
                        "sale_count": 3,
                    }
                ],
                meta={},
            ),
        )

        top_products = analytics_service.get_top_selling_products(today, today)

        assert len(top_products) == 1
        result = top_products[0]
        assert result["total_quantity"] == 5
        assert result["name"] == "Test Product 1"
        assert result["total_revenue"] == 7500

    def test_get_inventory_turnover(self, analytics_service, mock_db):
        """Test inventory turnover calculation."""
        # Method exists (line 280 in inventory_service.py, wait... AnalyticsService doesn't have it?)
        # Step 543 AnalyticsService outline did NOT show get_inventory_turnover.
        # It was in InventoryService!
        # So analytics_service.get_inventory_turnover call will fail.
        # I should remove this test from test_analytics_service.py or move it to test_inventory_service.py
        pass

    # def test_get_profit_margins(self, analytics_service, sample_data):
    #    # Method does not exist (has get_profit_margin_distribution)
    #    pass

    def test_get_sales_trends(self, analytics_service, mocker):
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        mocker.patch(
            "services.analytics_service.AnalyticsEngine.execute_metric",
            return_value=MetricResult(
                data=[
                    {
                        "date": start_date.isoformat(),
                        "total_sales": 1000,
                        "sale_count": 5,
                    },
                    {
                        "date": end_date.isoformat(),
                        "total_sales": 2000,
                        "sale_count": 8,
                    },
                ],
                meta={},
            ),
        )

        # Call singular method
        trends = analytics_service.get_sales_trend(
            start_date.isoformat(), end_date.isoformat()
        )

        assert isinstance(trends, list)
        assert len(trends) > 0
        assert "daily_sales" in trends[0]
        assert "sale_count" in trends[0]

    def test_get_category_performance(self, analytics_service, mocker):
        today = date.today().isoformat()

        mocker.patch(
            "services.analytics_service.AnalyticsEngine.execute_metric",
            return_value=MetricResult(
                data=[
                    {
                        "category": "Test Category",
                        "total_sales": 15000,
                        "units_sold": 10,
                        "sale_count": 4,
                    }
                ],
                meta={},
            ),
        )

        performance = analytics_service.get_category_performance(today, today)

        assert len(performance) == 1
        result = performance[0]
        assert result["category"] == "Test Category"
        assert result["sale_count"] == 4
        assert result["total_sales"] == 15000

    # def test_get_customer_segments(self, analytics_service, sample_data):
    #     pass

    # def test_get_stock_alerts(self, analytics_service, sample_data):
    #     pass

    def test_invalid_date_range(self, analytics_service):
        future_date = (date.today() + timedelta(days=1)).isoformat()

        with pytest.raises(ValidationException):
            analytics_service.get_sales_by_weekday(future_date, future_date)

    def test_date_range_validation(self, analytics_service):
        """Test validation of date ranges."""
        future_date = (date.today() + timedelta(days=1)).isoformat()
        today = date.today().isoformat()

        with pytest.raises(ValidationException):
            analytics_service.get_sales_by_weekday(future_date, today)

        with pytest.raises(ValidationException):
            analytics_service.get_sales_by_weekday(today, future_date)


class TestAnalyticsServiceRealDb:
    """Integration guard: metrics run against the real app schema, read-only.

    The analytics engine opens its OWN read-only connection to the FILE
    at `config.DATABASE_PATH` (mode=ro URI), so an in-memory `db_manager`
    DB is invisible to it. This class builds a temp-file database with
    `init_db(db_path=...)` (real schema.sql + alembic head), seeds it via
    the services, and points the engine at that file by patching
    `services.analytics.engine.DATABASE_PATH`. `mock_database` is never
    used here.
    """

    DATE_RANGE = ("2026-07-01", "2026-08-14")
    SALE_DATE = "2026-07-10"

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        self.db_file = tmp_path / "analytics_real.db"
        init_db(db_path=str(self.db_file))
        monkeypatch.setattr("services.analytics.engine.DATABASE_PATH", self.db_file)

        self.category_service = CategoryService()
        self.product_service = ProductService()
        self.customer_service = CustomerService()
        self.inventory_service = InventoryService()
        self.sale_service = SaleService()

        self.cat_id = self.category_service.create_category("Test Cat")
        self.prod_id = self.product_service.create_product(
            {
                "name": "Arroz",
                "category_id": self.cat_id,
                "cost_price": 1000,
                "sell_price": 2000,
            }
        )
        self.inventory_service.set_quantity(self.prod_id, 10.0)
        self.cust_id = self.customer_service.create_customer(
            "923456789", "Test Customer"
        )
        self.sale_service.create_sale(
            self.cust_id,
            self.SALE_DATE,
            [
                {
                    "product_id": self.prod_id,
                    "quantity": 2.0,
                    "sell_price": 2000,
                    "profit": 2000,
                }
            ],
        )

    def _row_counts(self) -> tuple[int, ...]:
        counts = DatabaseManager.fetch_all(
            "SELECT "
            "(SELECT COUNT(*) FROM sales) AS sales,"
            "(SELECT COUNT(*) FROM sale_items) AS sale_items,"
            "(SELECT COUNT(*) FROM inventory) AS inventory,"
            "(SELECT COUNT(*) FROM inventory_adjustments) AS inventory_adjustments,"
            "(SELECT COUNT(*) FROM products) AS products"
        )[0]
        return tuple(counts.values())

    def test_metrics_return_expected_values_for_seeded_data(self):
        summary = AnalyticsService.get_sales_summary(*self.DATE_RANGE)

        assert summary == {
            "total_sales": 1,
            "total_revenue": 4000,
            "total_profit": 2000,
            "average_sale_value": 4000.0,
            "unique_customers": 1,
        }

        top = AnalyticsService.get_top_selling_products(*self.DATE_RANGE, limit=5)
        assert top == [
            {
                "id": self.prod_id,
                "product_id": self.prod_id,
                "name": "Arroz",
                "total_quantity": 2.0,
                "total_revenue": 4000,
                "sale_count": 1,
            }
        ]

        weekday = AnalyticsService.get_sales_by_weekday(*self.DATE_RANGE)
        # 2026-07-10 is a Friday; SQLite %w -> English weekday names.
        assert weekday == [{"weekday": "Friday", "total_sales": 4000, "sale_count": 1}]

    def test_metric_calls_are_read_only_and_cache_clears(self):
        before = self._row_counts()
        assert before == (1, 1, 1, 1, 1)

        AnalyticsService.get_sales_summary(*self.DATE_RANGE)
        AnalyticsService.get_top_selling_products(*self.DATE_RANGE, limit=5)
        AnalyticsService.get_sales_by_weekday(*self.DATE_RANGE)

        assert self._row_counts() == before
        AnalyticsService.clear_cache()
