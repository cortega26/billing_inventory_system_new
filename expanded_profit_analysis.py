import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from config import DATABASE_PATH
from utils.system.logger import logger

def analyze_and_fix_sales():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Step 1: Analyze the structure (unchanged)
        cursor.execute("PRAGMA table_info(sales)")
        sales_columns = [column[1] for column in cursor.fetchall()]
        print("Sales table columns:", sales_columns)

        cursor.execute("PRAGMA table_info(sale_items)")
        sale_items_columns = [column[1] for column in cursor.fetchall()]
        print("Sale items table columns:", sale_items_columns)

        # Step 2: Retrieve sales data (expanded query)
        cursor.execute("""
            SELECT 
                s.id, 
                s.total_amount, 
                s.total_profit, 
                SUM(si.quantity * si.price) as calculated_total,
                SUM((si.price - COALESCE(p.cost_price, 0)) * si.quantity) as calculated_profit,
                MIN((si.price - COALESCE(p.cost_price, 0)) * si.quantity) as min_item_profit
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            LEFT JOIN products p ON si.product_id = p.id
            GROUP BY s.id
        """)
        sales_data = cursor.fetchall()

        # Step 3: Analyze and fix discrepancies (expanded checks)
        for sale in sales_data:
            sale_id, total_amount, total_profit, calculated_total, calculated_profit, min_item_profit = sale
            
            # Convert to Decimal for precise comparison
            total_amount = Decimal(str(total_amount))
            total_profit = Decimal(str(total_profit))
            calculated_total = Decimal(str(calculated_total))
            calculated_profit = Decimal(str(calculated_profit))
            min_item_profit = Decimal(str(min_item_profit))

            issues = []

            if abs(total_amount - calculated_total) > Decimal('0.01'):
                issues.append(f"Total amount discrepancy: {total_amount} vs {calculated_total}")

            if abs(total_profit - calculated_profit) > Decimal('0.01'):
                issues.append(f"Total profit discrepancy: {total_profit} vs {calculated_profit}")

            if total_profit < Decimal('0'):
                issues.append(f"Negative total profit: {total_profit}")

            if calculated_profit < Decimal('0'):
                issues.append(f"Negative calculated profit: {calculated_profit}")

            if min_item_profit < Decimal('0'):
                issues.append(f"Negative profit on individual item: {min_item_profit}")

            if issues:
                print(f"Issues found for sale {sale_id}:")
                for issue in issues:
                    print(f"  - {issue}")

                # Update the profit if there's a discrepancy or it's negative
                if total_profit != calculated_profit or total_profit < Decimal('0'):
                    new_profit = max(calculated_profit, Decimal('0'))  # Ensure non-negative profit
                    cursor.execute("""
                        UPDATE sales
                        SET total_profit = ?
                        WHERE id = ?
                    """, (float(new_profit), sale_id))
                    print(f"  Updated total_profit to {new_profit}")

                # Retrieve and display individual sale items for problematic sales
                cursor.execute("""
                    SELECT si.product_id, p.name, si.quantity, si.price, p.cost_price
                    FROM sale_items si
                    LEFT JOIN products p ON si.product_id = p.id
                    WHERE si.sale_id = ?
                """, (sale_id,))
                items = cursor.fetchall()
                print("  Sale items:")
                for item in items:
                    product_id, name, quantity, price, cost_price = item
                    item_profit = (Decimal(str(price)) - Decimal(str(cost_price or 0))) * Decimal(str(quantity))
                    print(f"    - Product ID: {product_id}, Name: {name}, Quantity: {quantity}, "
                          f"Price: {price}, Cost Price: {cost_price}, Profit: {item_profit}")

        conn.commit()
        print("Analysis and fixes completed.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"An error occurred: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_and_fix_sales()
