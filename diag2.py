import os
from services.sale_service import SaleService
from database import DatabaseManager
from datetime import datetime

def diagnose_sales_data():
    # Create a directory for diagnostic reports if it doesn't exist
    reports_dir = "diagnostic_reports"
    os.makedirs(reports_dir, exist_ok=True)

    # Generate a unique filename based on the current timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(reports_dir, f"sales_diagnostic_{timestamp}.txt")

    with open(filename, 'w') as f:
        f.write("Sales Diagnostic Report\n")
        f.write("=======================\n\n")

        # Diagnose sales table
        f.write("Sales Table:\n")
        f.write("------------\n")
        query = "SELECT * FROM sales"
        rows = DatabaseManager.fetch_all(query)
        for row in rows:
            f.write(f"Sale ID: {row['id']}\n")
            f.write(f"  customer_id: {row['customer_id']}\n")
            f.write(f"  date: {row['date']}\n")
            f.write(f"  total_amount: {row['total_amount']}\n")
            f.write(f"  total_profit: {row['total_profit']}\n")
            f.write(f"  receipt_id: {row['receipt_id']}\n")
            f.write("---\n")

        f.write("\nSale Items Table:\n")
        f.write("------------------\n")
        query = "SELECT * FROM sale_items"
        rows = DatabaseManager.fetch_all(query)
        for row in rows:
            f.write(f"Sale Item ID: {row['id']}\n")
            f.write(f"  sale_id: {row['sale_id']}\n")
            f.write(f"  product_id: {row['product_id']}\n")
            f.write(f"  quantity: {row['quantity']}\n")
            f.write(f"  price: {row['price']}\n")
            f.write(f"  profit: {row['profit']}\n")
            f.write("---\n")

    print(f"Diagnostic report has been written to {filename}")

if __name__ == "__main__":
    diagnose_sales_data()
