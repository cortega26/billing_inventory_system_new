import pytest
from datetime import datetime, date, timedelta
from services.analytics_service import AnalyticsService
from services.sale_service import SaleService
from services.purchase_service import PurchaseService
from services.product_service import ProductService
from services.inventory_service import InventoryService
from models.product import Product
from utils.exceptions import ValidationException
from decimal import Decimal
from tests.utils.test_helpers import create_test_product_data, generate_unique_barcode
from tests.utils.base_test import BaseTest

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

@pytest.fixture
def sample_data(product_service, inventory_service, mocker):
    """Create sample data for analytics tests."""
    products = []
    for i in range(1, 4):
        product_data = create_test_product_data(
            barcode=generate_unique_barcode()
        )
        
        # Mock product creation
        mock_execute = mocker.patch('database.database_manager.DatabaseManager.execute_query')
        mock_execute.return_value.lastrowid = i
        
        product_id = product_service.create_product(product_data)
        products.append(product_service.get_product(product_id))
        
        # Create inventory
        inventory_service.create_inventory(product_id, 100.0)
    
    return {"products": products}

@pytest.fixture
def sample_product(self):
    return Product(
        id=1,
        name="Test Product",
        description="Test Description",
        category_id=1,
        cost_price=1000.0,
        sell_price=1500.0,
        barcode="12345678"
    )

class TestAnalyticsService(BaseTest):
    def test_get_sales_by_weekday(self, analytics_service, mock_db):
        # Setup mock data
        self.setup_mock_db_response(
            mock_db,
            fetch_all_return=[{
                'day_of_week': 1,
                'total_amount': 1500.0,
                'sale_count': 5
            }]
        )
        
        # Test
        today = date.today().isoformat()
        sales_by_weekday = analytics_service.get_sales_by_weekday(today, today)
        
        # Verify
        assert len(sales_by_weekday) > 0
        assert isinstance(sales_by_weekday[0]["total_amount"], float)
        assert isinstance(sales_by_weekday[0]["sale_count"], int)

    def test_get_sales_by_hour(self, analytics_service, sample_data):
        today = date.today().isoformat()
        sales_by_hour = analytics_service.get_sales_by_hour(today, today)
        
        assert len(sales_by_hour) > 0
        assert all(isinstance(hour["hour"], int) for hour in sales_by_hour)
        assert all(isinstance(hour["sale_count"], int) for hour in sales_by_hour)

    def test_get_top_selling_products(self, analytics_service, mock_db):
        """Test getting top selling products."""
        today = date.today().isoformat()
        
        # Setup mock data
        mock_data = [{
            'product_id': 1,
            'product_name': 'Test Product 1',
            'quantity_sold': 5,
            'total_amount': 7500.0,
            'created_at': today,
            'updated_at': today
        }]
        
        self.setup_mock_db_response(
            mock_db,
            fetch_all_return=mock_data
        )
        
        # Execute test
        top_products = analytics_service.get_top_selling_products(today, today)
        
        # Verify results
        assert len(top_products) == 1
        result = top_products[0]
        assert result["quantity_sold"] == 5
        assert result["product_name"] == "Test Product 1"
        assert result["total_amount"] == 7500.0

    def test_get_inventory_turnover(self, analytics_service, mock_db):
        """Test inventory turnover calculation."""
        today = date.today().isoformat()
        
        # Setup mock data
        mock_data = [{
            'product_id': 1,
            'product_name': 'Test Product 1',
            'turnover_ratio': 0.5,
            'quantity_sold': 50,
            'average_inventory': 100,
            'created_at': today,
            'updated_at': today
        }]
        
        # Setup mock response
        self.setup_mock_db_response(
            mock_db,
            fetch_all_return=mock_data
        )
        
        # Execute test
        turnover_data = analytics_service.get_inventory_turnover(today, today)
        
        # Verify results
        assert len(turnover_data) == 1
        result = turnover_data[0]
        assert isinstance(result["turnover_ratio"], float)
        assert result["turnover_ratio"] == 0.5
        assert result["product_name"] == "Test Product 1"
        assert result["quantity_sold"] == 50
        assert result["average_inventory"] == 100

    def test_get_profit_margins(self, analytics_service, sample_data):
        today = date.today().isoformat()
        margins = analytics_service.get_profit_margins(today, today)
        
        assert len(margins) > 0
        assert all(isinstance(m["margin"], (float, Decimal)) for m in margins)
        assert all(m["margin"] >= 0 for m in margins)

    def test_get_sales_trends(self, analytics_service, sample_data):
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        trends = analytics_service.get_sales_trends(start_date.isoformat(), end_date.isoformat())
        
        assert isinstance(trends, dict)
        assert "daily_averages" in trends
        assert "weekly_totals" in trends
        assert "monthly_totals" in trends

    def test_get_category_performance(self, analytics_service, mock_db):
        """Test getting category performance metrics."""
        today = date.today().isoformat()
        
        # Setup mock data
        mock_data = [{
            'category_id': 1,
            'category_name': 'Test Category',
            'sale_count': 10,
            'total_amount': 15000.0,
            'created_at': today,
            'updated_at': today
        }]
        
        self.setup_mock_db_response(
            mock_db,
            fetch_all_return=mock_data
        )
        
        # Execute test
        performance = analytics_service.get_category_performance(today, today)
        
        # Verify results
        assert len(performance) == 1
        result = performance[0]
        assert result["category_name"] == "Test Category"
        assert result["sale_count"] == 10
        assert result["total_amount"] == 15000.0

    def test_get_customer_segments(self, analytics_service, sample_data):
        today = date.today().isoformat()
        segments = analytics_service.get_customer_segments(today, today)
        
        assert isinstance(segments, dict)
        assert "high_value" in segments
        assert "regular" in segments
        assert "occasional" in segments

    def test_get_stock_alerts(self, analytics_service, sample_data):
        alerts = analytics_service.get_stock_alerts()
        
        assert isinstance(alerts, list)
        assert all(isinstance(a["product_id"], int) for a in alerts)
        assert all(isinstance(a["current_stock"], (int, float, Decimal)) for a in alerts)

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