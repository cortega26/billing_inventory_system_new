import sqlite3
from config import DATABASE_PATH
from utils.system.logger import logger
from decimal import Decimal, ROUND_HALF_UP

def fix_profit_calculations():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Step 1: Retrieve all sale items
        cursor.execute("""
            SELECT si.id, si.sale_id, si.product_id, si.quantity, si.price, p.cost_price
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
        """)
        sale_items = cursor.fetchall()

        # Step 2: Recalculate profits with high precision
        for item in sale_items:
            item_id, sale_id, product_id, quantity, price, cost_price = item
            
            # Use Decimal for high precision calculation
            quantity_dec = Decimal(str(quantity))
            price_dec = Decimal(str(price))
            cost_price_dec = Decimal(str(cost_price)) if cost_price is not None else Decimal('0')

            # Calculate profit
            profit = (price_dec - cost_price_dec) * quantity_dec
            
            # Round to 2 decimal places
            profit = profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Update the sale_items table
            cursor.execute("""
                UPDATE sale_items
                SET profit = ?
                WHERE id = ?
            """, (float(profit), item_id))

        # Step 3: Recalculate total profits for each sale
        cursor.execute("""
            UPDATE sales
            SET total_profit = (
                SELECT COALESCE(SUM(profit), 0)
                FROM sale_items
                WHERE sale_items.sale_id = sales.id
            )
        """)

        conn.commit()
        logger.info("Profit recalculation completed successfully")

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"An error occurred during profit recalculation: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_profit_calculations()