from typing import List, Dict, Any, Optional
from database import DatabaseManager
from models.sale import Sale, SaleItem
from services.inventory_service import InventoryService
from utils.decorators import db_operation, validate_input
from utils.exceptions import ValidationException
from functools import lru_cache
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


class SaleService:
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def create_sale(self, customer_id: int, date: str, items: List[Dict[str, Any]]) -> Optional[int]:
        SaleService._validate_sale_items(items)
        total_amount = sum(item["quantity"] * item["sell_price"] for item in items)

        receipt_id = self.generate_receipt_id(datetime.fromisoformat(date))

        query = "INSERT INTO sales (customer_id, date, total_amount, receipt_id) VALUES (?, ?, ?, ?)"
        cursor = DatabaseManager.execute_query(query, (customer_id, date, total_amount, receipt_id))
        sale_id = cursor.lastrowid

        if sale_id is None:
            raise ValidationException("Failed to create sale record")

        self._insert_sale_items(sale_id, items)
        self._update_inventory(items)

        self.clear_cache()
        return sale_id

    @db_operation(show_dialog=True)
    def get_sale(self, sale_id: int) -> Optional[Sale]:
        query = """
        SELECT s.*, 
            COALESCE(s.receipt_id, '') as receipt_id  -- Use COALESCE to handle NULL values
        FROM sales s
        WHERE s.id = ?
        """
        row = DatabaseManager.fetch_one(query, (sale_id,))
        if row:
            sale = Sale.from_db_row(row)
            sale.items = self.get_sale_items(sale_id)
            return sale
        return None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    def get_all_sales() -> List[Sale]:
        query = "SELECT * FROM sales ORDER BY date DESC"
        rows = DatabaseManager.fetch_all(query)
        sales = [Sale.from_db_row(row) for row in rows]
        for sale in sales:
            sale.items = SaleService.get_sale_items(sale.id)
        return sales

    @staticmethod
    @db_operation(show_dialog=True)
    def get_sale_items(sale_id: int) -> List[SaleItem]:
        query = "SELECT * FROM sale_items WHERE sale_id = ?"
        rows = DatabaseManager.fetch_all(query, (sale_id,))
        return [SaleItem.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    def delete_sale(sale_id: int) -> None:
        items = SaleService.get_sale_items(sale_id)

        SaleService._revert_inventory(items)

        DatabaseManager.execute_query(
            "DELETE FROM sale_items WHERE sale_id = ?", (sale_id,)
        )
        DatabaseManager.execute_query("DELETE FROM sales WHERE id = ?", (sale_id,))
        SaleService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def get_total_sales(start_date: str, end_date: str) -> float:
        query = """
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ?
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        return float(result["total"] if result else 0)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_sales_by_customer(customer_id: int) -> List[Sale]:
        query = "SELECT * FROM sales WHERE customer_id = ? ORDER BY date DESC"
        rows = DatabaseManager.fetch_all(query, (customer_id,))
        sales = [Sale.from_db_row(row) for row in rows]
        for sale in sales:
            sale.items = SaleService.get_sale_items(sale.id)
        return sales

    @staticmethod
    @db_operation(show_dialog=True)
    def get_top_selling_products(
        start_date: str, end_date: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT p.id, p.name, SUM(si.quantity) as total_quantity, SUM(si.quantity * si.price) as total_revenue
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY total_quantity DESC
            LIMIT ?
        """
        return DatabaseManager.fetch_all(query, (start_date, end_date, limit))

    @staticmethod
    @db_operation(show_dialog=True)
    def get_daily_sales(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = """
            SELECT date, SUM(total_amount) as daily_total
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """
        return DatabaseManager.fetch_all(query, (start_date, end_date))

    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def update_sale(self, sale_id: int, customer_id: int, date: str, items: List[Dict[str, Any]]) -> None:
        sale = self.get_sale(sale_id)
        if not sale:
            raise ValidationException(f"Sale with ID {sale_id} not found.")

        sale_datetime = datetime.fromisoformat(sale.date.isoformat())
        if datetime.now() - sale_datetime > timedelta(hours=48):
            raise ValidationException("Sales can only be edited within 48 hours of creation.")

        self._validate_sale_items(items)
        old_items = self.get_sale_items(sale_id)

        self._revert_inventory(old_items)

        total_amount = sum(item["sell_price"] * item["quantity"] for item in items)

        self._update_sale(sale_id, customer_id, date, total_amount)
        self._update_sale_items(sale_id, items)
        self._update_inventory(items)

        self.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def get_sales_stats(start_date: str, end_date: str) -> Dict[str, Any]:
        query = """
        SELECT 
            COUNT(DISTINCT s.id) as total_sales,
            SUM(s.total_amount) as total_revenue,
            AVG(s.total_amount) as average_sale_amount,
            COUNT(DISTINCT s.customer_id) as unique_customers
        FROM sales s
        WHERE s.date BETWEEN ? AND ?
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        return {
            "total_sales": result["total_sales"] if result else 0,
            "total_revenue": (
                float(result["total_revenue"])
                if result and result["total_revenue"]
                else 0.0
            ),
            "average_sale_amount": (
                float(result["average_sale_amount"])
                if result and result["average_sale_amount"]
                else 0.0
            ),
            "unique_customers": result["unique_customers"] if result else 0,
        }

    @staticmethod
    @db_operation(show_dialog=True)
    def get_total_sales_by_customer(customer_id: int) -> float:
        query = """
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE customer_id = ?
        """
        result = DatabaseManager.fetch_one(query, (customer_id,))
        return float(result["total"] if result else 0)

    @staticmethod
    def generate_receipt_id(sale_date: datetime) -> str:
        date_part = sale_date.strftime("%y%m%d")
        
        # Get the last receipt number for this date
        query = """
            SELECT MAX(SUBSTR(receipt_id, 7)) as last_number
            FROM sales
            WHERE receipt_id LIKE ?
        """
        result = DatabaseManager.fetch_one(query, (f"{date_part}%",))
        
        last_number = int(result['last_number']) if result and result['last_number'] is not None else 0
        new_number = last_number + 1
        
        return f"{date_part}{new_number:03d}"

    @db_operation(show_dialog=True)
    def generate_receipt(self, sale_id: int) -> str:
        sale = self.get_sale(sale_id)
        if not sale:
            raise ValidationException(f"Sale with ID {sale_id} not found.")

        if not sale.receipt_id:
            receipt_id = self.generate_receipt_id(sale.date)
            self._update_sale_receipt_id(sale_id, receipt_id)
            sale.receipt_id = receipt_id
        else:
            receipt_id = sale.receipt_id

        return receipt_id

    @db_operation(show_dialog=True)
    def _update_sale_receipt_id(self, sale_id: int, receipt_id: str) -> None:
        query = "UPDATE sales SET receipt_id = ? WHERE id = ?"
        DatabaseManager.execute_query(query, (receipt_id, sale_id))

    def save_receipt_as_pdf(self, sale_id: int, filepath: str) -> None:
        sale = self.get_sale(sale_id)
        if not sale:
            raise ValidationException(f"Sale with ID {sale_id} not found.")

        items = self.get_sale_items(sale_id)
        
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter

        # Set up the document
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, f"Receipt #{sale.receipt_id}")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 80, f"Date: {sale.date.strftime('%Y-%m-%d')}")
        c.drawString(50, height - 100, f"Customer ID: {sale.customer_id}")

        # Draw items
        y = height - 150
        c.drawString(50, y, "Product")
        c.drawString(250, y, "Quantity")
        c.drawString(350, y, "Price")
        c.drawString(450, y, "Total")

        y -= 20
        for item in items:
            c.drawString(50, y, item.product_name or f"Product ID: {item.product_id}")
            c.drawString(250, y, str(item.quantity))
            c.drawString(350, y, f"${item.unit_price:.2f}")
            c.drawString(450, y, f"${item.total_price():.2f}")
            y -= 20

        c.drawString(350, y - 20, "Total:")
        c.drawString(450, y - 20, f"${sale.total_amount:.2f}")

        c.save()

    def send_receipt_via_whatsapp(self, sale_id: int, phone_number: str) -> None:
        # This is a placeholder. You'll need to implement the actual WhatsApp API integration.
        # For now, we'll just print a message.
        print(f"Sending receipt for sale {sale_id} to WhatsApp number {phone_number}")

    @staticmethod
    def clear_cache():
        SaleService.get_all_sales.cache_clear()

    @staticmethod
    def _validate_sale_items(items: List[Dict[str, Any]]) -> None:
        if not items:
            raise ValidationException("Sale must have at least one item")
        for item in items:
            if item["quantity"] <= 0 or item["sell_price"] <= 0:
                raise ValidationException(
                    "Item quantity and sell price must be positive"
                )

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_sale(customer_id: int, date: str, total_amount: float) -> Optional[int]:
        query = "INSERT INTO sales (customer_id, date, total_amount) VALUES (?, ?, ?)"
        cursor = DatabaseManager.execute_query(query, (customer_id, date, total_amount))
        return cursor.lastrowid

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        for item in items:
            query = """
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            """
            DatabaseManager.execute_query(
                query,
                (sale_id, item["product_id"], item["quantity"], item["sell_price"]),
            )

    @staticmethod
    def _update_inventory(items: List[Dict[str, Any]]) -> None:
        for item in items:
            InventoryService.update_quantity(item["product_id"], -item["quantity"])

    @staticmethod
    def _revert_inventory(items: List[SaleItem]) -> None:
        for item in items:
            InventoryService.update_quantity(item.product_id, item.quantity)

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale(
        sale_id: int, customer_id: int, date: str, total_amount: float
    ) -> None:
        query = (
            "UPDATE sales SET customer_id = ?, date = ?, total_amount = ? WHERE id = ?"
        )
        DatabaseManager.execute_query(query, (customer_id, date, total_amount, sale_id))

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        DatabaseManager.execute_query(
            "DELETE FROM sale_items WHERE sale_id = ?", (sale_id,)
        )
        SaleService._insert_sale_items(sale_id, items)
