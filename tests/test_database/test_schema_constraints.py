
import pytest
import sqlite3
from database.database_manager import DatabaseManager
from utils.exceptions import DatabaseException

class TestSchemaConstraints:
    
    def test_foreign_key_on_delete_restrict(self, db_manager):
        """Test that products cannot be deleted if they are used in sale_items (ON DELETE RESTRICT)."""
        # Create a product
        cursor = DatabaseManager.execute_query(
            "INSERT INTO products (name, cost_price, sell_price, category_id) VALUES (?, ?, ?, ?)",
            ("Test Product", 100, 200, None)
        )
        product_id = cursor.lastrowid
        
        # Create a customer (needed for sale foreign key)
        cursor = DatabaseManager.execute_query(
            "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
            ("TEST12345", "Test Customer")
        )
        customer_id = cursor.lastrowid

        # Create a sale and sale item using this product
        cursor = DatabaseManager.execute_query(
            "INSERT INTO sales (customer_id, date, total_amount, total_profit) VALUES (?, ?, ?, ?)",
            (customer_id, "2023-01-01", 200, 100)
        )
        sale_id = cursor.lastrowid
        
        DatabaseManager.execute_query(
            "INSERT INTO sale_items (sale_id, product_id, quantity, price, profit) VALUES (?, ?, ?, ?, ?)",
            (sale_id, product_id, 1, 200, 100)
        )
        
        # Try to delete the product - should fail
        with pytest.raises(DatabaseException) as excinfo:
            DatabaseManager.execute_query("DELETE FROM products WHERE id = ?", (product_id,))
        
        # Verify specific error for constraint violation (SQLite error code 787 or similar)
        # Note: DatabaseManager wraps exceptions, so we check the string message or inner exception
        assert "FOREIGN KEY constraint failed" in str(excinfo.value) or "constraint failed" in str(excinfo.value)

    def test_check_constraint_positive_price(self, db_manager):
        """Test that products cannot have negative prices (CHECK constraint)."""
        
        with pytest.raises(DatabaseException) as excinfo:
             DatabaseManager.execute_query(
                "INSERT INTO products (name, cost_price, sell_price) VALUES (?, ?, ?)",
                ("Negative Price Product", -100, 200)
            )
        # Message might be "CHECK constraint failed" (raw) or "Query execution failed: ... CHECK constraint failed" (wrapped)
        assert "constraint failed" in str(excinfo.value)

    def test_check_constraint_positive_inventory(self, db_manager):
        """Test that inventory quantity cannot be negative (CHECK constraint)."""
        
        # Create a product first
        cursor = DatabaseManager.execute_query(
            "INSERT INTO products (name, cost_price, sell_price) VALUES (?, ?, ?)",
            ("Inv Product", 100, 200)
        )
        product_id = cursor.lastrowid
        
        with pytest.raises(DatabaseException) as excinfo:
            DatabaseManager.execute_query(
                "INSERT INTO inventory (product_id, quantity) VALUES (?, ?)",
                (product_id, -5.0)
            )
        # Message might be "CHECK constraint failed" (raw) or "Query execution failed: ... CHECK constraint failed" (wrapped)
        assert "constraint failed" in str(excinfo.value)

    def test_foreign_key_cascade_on_sale_delete(self, db_manager):
        """Test that sale_items are deleted when sale is deleted (ON DELETE CASCADE)."""
        # Create product, sale, sale_items
        cursor = DatabaseManager.execute_query(
            "INSERT INTO products (name, cost_price, sell_price) VALUES (?, ?, ?)",
            ("Cascade Product", 100, 200)
        )
        product_id = cursor.lastrowid
        
        cursor = DatabaseManager.execute_query(
             "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
            ("TESTCASCADE", "Cascade Customer")
        )
        customer_id = cursor.lastrowid

        cursor = DatabaseManager.execute_query(
            "INSERT INTO sales (customer_id, date, total_amount, total_profit) VALUES (?, ?, ?, ?)",
            (customer_id, "2023-01-01", 0, 0)
        )
        sale_id = cursor.lastrowid
        
        DatabaseManager.execute_query(
            "INSERT INTO sale_items (sale_id, product_id, quantity, price, profit) VALUES (?, ?, ?, ?, ?)",
            (sale_id, product_id, 1, 200, 100)
        )
        
        # Verify item exists
        items = DatabaseManager.fetch_all("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
        assert len(items) == 1
        
        # Delete sale
        DatabaseManager.execute_query("DELETE FROM sales WHERE id = ?", (sale_id,))
        
        # Verify item is gone
        items = DatabaseManager.fetch_all("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
        assert len(items) == 0

