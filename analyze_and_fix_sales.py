import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from config import DATABASE_PATH
from utils.system.logger import logger

def analyze_and_fix_sales():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Step 1: Analyze the structure
        cursor.execute("PRAGMA table_info(sales)")
        sales_columns = [column[1] for column in cursor.fetchall()]
        print("Sales table columns:", sales_columns)

        cursor.execute("PRAGMA table_info(sale_items)")
        sale_items_columns = [column[1] for column in cursor.fetchall()]
        print("Sale items table columns:", sale_items_columns)

        # Step 2: Retrieve sales data
        cursor.execute("""
            SELECT s.id, s.total_amount, s.total_profit, 
                   SUM(si.quantity * si.price) as calculated_total,
                   SUM((si.price - COALESCE(p.cost_price, 0)) * si.quantity) as calculated_profit
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            LEFT JOIN products p ON si.product_id = p.id
            GROUP BY s.id
        """)
        sales_data = cursor.fetchall()

        # Step 3: Analyze and fix discrepancies
        for sale in sales_data:
            sale_id, total_amount, total_profit, calculated_total, calculated_profit = sale
            
            if abs(Decimal(str(total_amount)) - Decimal(str(calculated_total))) > Decimal('0.01'):
                print(f"Discrepancy in total amount for sale {sale_id}: {total_amount} vs {calculated_total}")
            
            if abs(Decimal(str(total_profit)) - Decimal(str(calculated_profit))) > Decimal('0.01'):
                print(f"Discrepancy in total profit for sale {sale_id}: {total_profit} vs {calculated_profit}")
                
                # Update the profit
                cursor.execute("""
                    UPDATE sales
                    SET total_profit = ?
                    WHERE id = ?
                """, (calculated_profit, sale_id))

        conn.commit()
        print("Analysis and fixes completed.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"An error occurred: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_and_fix_sales()