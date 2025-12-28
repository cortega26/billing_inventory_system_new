import pytest
from utils.math.financial_calculator import FinancialCalculator

class TestFinancialCalculator:
    def test_calculate_item_total_simple(self):
        # 2 * 1000 = 2000
        assert FinancialCalculator.calculate_item_total(2.0, 1000) == 2000

    def test_calculate_item_total_decimal_qty(self):
        # 1.5 * 1000 = 1500
        assert FinancialCalculator.calculate_item_total(1.5, 1000) == 1500
        
    def test_calculate_item_total_rounding(self):
        # 1.333 * 1000 = 1333
        assert FinancialCalculator.calculate_item_total(1.333, 1000) == 1333
        
        # 0.5 * 1 = 0.5 -> rounds to 1 (ROUND_HALF_UP)
        assert FinancialCalculator.calculate_item_total(0.5, 1) == 1
        
        # 0.4 * 1 = 0.4 -> rounds to 0
        assert FinancialCalculator.calculate_item_total(0.4, 1) == 0

    def test_calculate_item_profit(self):
        # Qty 2, Sell 1000, Cost 500 => 2 * (1000 - 500) = 1000
        assert FinancialCalculator.calculate_item_profit(2.0, 1000, 500) == 1000

    def test_calculate_item_profit_decimal(self):
        # Qty 1.5, Sell 100, Cost 50 => 1.5 * 50 = 75
        assert FinancialCalculator.calculate_item_profit(1.5, 100, 50) == 75

    def test_calculate_sale_totals(self):
        items = [
            {"quantity": 2, "sell_price": 100, "profit": 50},
            {"quantity": 1, "sell_price": 200, "profit": 100}
        ]
        # Total: (2*100) + (1*200) = 400
        # Profit: 50 + 100 = 150
        result = FinancialCalculator.calculate_sale_totals(items)
        assert result["total_amount"] == 400
        assert result["total_profit"] == 150

    def test_round_quantity(self):
        assert FinancialCalculator.round_quantity(1.12345) == 1.123
        assert FinancialCalculator.round_quantity(1.1236) == 1.124
