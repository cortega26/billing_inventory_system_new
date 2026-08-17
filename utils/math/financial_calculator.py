from decimal import ROUND_HALF_UP, Decimal


class FinancialCalculator:
    """
    Centralized calculator for financial operations to ensure consistency
    in rounding and business logic across the application (Services and UI).
    """

    @staticmethod
    def _to_decimal(value: int | float | Decimal | str) -> Decimal:
        if isinstance(value, float):
            return Decimal(
                str(value)
            )  # Convert float to string first to avoid precision issues
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
        total = (qty * price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
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

        profit = (qty * (s_price - c_price)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return int(profit)
