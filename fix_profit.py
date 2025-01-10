#!/usr/bin/env python3
"""
Fix total_profit calculations in the sales DB.
1) For each sale_item:
   - Recompute line profit = quantity * (price - cost_price)
   - Update sale_items.profit
2) Recompute the sales.total_profit as sum of sale_items.profit
   - Update the sales table
"""

import sqlite3

DB_PATH = "billing_inventory.db"  # Adjust if needed

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1) Retrieve cost_price from products for each sale_item
    #    Then compute the correct profit for that item
    select_items = """
        SELECT 
            si.id AS sale_item_id,
            si.sale_id,
            si.product_id,
            si.quantity,
            si.price AS sell_price,
            si.profit AS old_profit,
            p.cost_price AS product_cost
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        -- Could also join 'sales s' if you need, e.g. s.date
    """
    items = conn.execute(select_items).fetchall()

    # This dictionary will map sale_id -> list of newly computed profits
    sales_to_item_profits = {}

    for row in items:
        sale_item_id = row["sale_item_id"]
        sale_id = row["sale_id"]
        cost_price = row["product_cost"] if row["product_cost"] is not None else 0
        quantity = float(row["quantity"])
        sell_price = int(row["sell_price"])
        old_profit = int(row["old_profit"]) if row["old_profit"] else 0

        # Compute correct line profit
        line_profit = int(round(quantity * (sell_price - cost_price)))

        # Update sale_items table with new profit
        update_item_sql = """
            UPDATE sale_items
            SET profit = ?
            WHERE id = ?
        """
        conn.execute(update_item_sql, (line_profit, sale_item_id))

        # Track in a local structure for recalculating sales total_profit
        if sale_id not in sales_to_item_profits:
            sales_to_item_profits[sale_id] = []
        sales_to_item_profits[sale_id].append(line_profit)

    # 2) Now recalc sales.total_profit as sum of new item profits
    for sale_id, item_profits in sales_to_item_profits.items():
        new_sale_profit = sum(item_profits)

        update_sale_sql = """
            UPDATE sales
            SET total_profit = ?
            WHERE id = ?
        """
        conn.execute(update_sale_sql, (new_sale_profit, sale_id))

    # Save changes
    conn.commit()
    conn.close()
    print("All total_profit values have been corrected.")

if __name__ == "__main__":
    main()
