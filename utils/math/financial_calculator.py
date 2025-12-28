from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Dict, Any, List

class FinancialCalculator:
    """
    Centralized calculator for financial operations to ensure consistency
    in rounding and business logic across the application (Services and UI).
    """
    
    # Constants from enums (redefined here or imported if preferred, but decoupled is safer for utils)
    # matching models.enums.QUANTITY_PRECISION
    QUANTITY_PRECISION = 3 
    
    @staticmethod
    def _to_decimal(value: Union[int, float, Decimal, str]) -> Decimal:
        if isinstance(value, float):
            return Decimal(str(value)) # Convert float to string first to avoid precision issues
        return Decimal(value)

    @staticmethod
    def calculate_item_total(quantity: float, unit_price: int) -> int:
        """
        Calculate the total price for an item line.
        Formula: round(quantity * unit_price)
        Returns an integer (CLP has no cents).
        """
        qty = FinancialCalculator._to_decimal(quantity)
        price = FinancialCalculator._to_decimal(unit_price)
        # Use ROUND_HALF_UP for standard rounding behavior (0.5 -> 1)
        total = (qty * price).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        return int(total)

    @staticmethod
    def calculate_item_profit(quantity: float, sell_price: int, cost_price: int) -> int:
        """
        Calculate the profit for an item line.
        Formula: round(quantity * (sell_price - cost_price))
        """
        if cost_price is None:
            cost_price = 0
            
        qty = FinancialCalculator._to_decimal(quantity)
        s_price = FinancialCalculator._to_decimal(sell_price)
        c_price = FinancialCalculator._to_decimal(cost_price)
        
        profit = (qty * (s_price - c_price)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        return int(profit)

    @staticmethod
    def calculate_sale_totals(items: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate total amount and total profit for a list of items.
        Expected item keys: 'quantity', 'sell_price', 'profit' (optional, if pre-calculated)
        If 'profit' is in item, it is summed. If not, it falls back to 0.
        
        Returns: {'total_amount': int, 'total_profit': int}
        """
        total_amount = 0
        total_profit = 0
        
        for item in items:
            # We assume item['quantity'] and item['sell_price'] exist
            qty = float(item['quantity'])
            price = int(item['sell_price'])
            
            # Recalculate line total to be safe, or direct sum?
            # Service logic was: item_total = round(qty * price)
            total_amount += FinancialCalculator.calculate_item_total(qty, price)
            
            # Profit
            # Service logic often passed 'profit' in the item dict
            if 'profit' in item:
                total_profit += int(item['profit'])
        
        return {
            "total_amount": total_amount,
            "total_profit": total_profit
        }

    @staticmethod
    def round_quantity(quantity: float) -> float:
        """
        Round quantity to the standard application precision.
        """
        return round(quantity, FinancialCalculator.QUANTITY_PRECISION)
