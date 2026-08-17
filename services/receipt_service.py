from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from database.database_manager import DatabaseManager
from models.sale import Sale
from utils.exceptions import NotFoundException, ValidationException
from utils.system.logger import logger
from utils.validation.validators import (
    validate_filepath,
    validate_integer,
    validate_string,
)


class ReceiptService:
    def generate_pdf(self, sale: Sale, items: list, filepath: str) -> None:
        """
        Generate a PDF receipt for a sale.

        Args:
            sale: The Sale object (with customer_id, receipt_id, dates, totals).
            items: List of SaleItem objects.
            filepath: Destination path for the PDF.
        """
        filepath = validate_filepath(filepath)

        try:
            c = canvas.Canvas(filepath, pagesize=letter)
            width, height = letter

            # Set up the document
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, f"Receipt #{sale.receipt_id}")

            c.setFont("Helvetica", 12)
            date_str = sale.date.strftime("%Y-%m-%d") if sale.date is not None else ""
            c.drawString(50, height - 80, f"Date: {date_str}")
            c.drawString(50, height - 100, f"Customer ID: {sale.customer_id}")

            # Draw items header
            y = height - 150
            c.drawString(50, y, "Product")
            c.drawString(250, y, "Quantity")
            c.drawString(350, y, "Price")
            c.drawString(450, y, "Total")

            y -= 20
            for item in items:
                # Handle potentially missing product names or use ID
                p_name = (
                    item.product_name
                    if hasattr(item, "product_name") and item.product_name
                    else f"Product ID: {item.product_id}"
                )

                c.drawString(50, y, p_name)
                c.drawString(250, y, str(item.quantity))
                c.drawString(350, y, f"${item.unit_price:,}".replace(",", "."))

                # item.total_price() is a method on SaleItem usually
                total_line = (
                    item.total_price()
                    if hasattr(item, "total_price")
                    else int(item.quantity * item.unit_price)
                )
                c.drawString(450, y, f"${total_line:,}".replace(",", "."))
                y -= 20

            # Totals
            c.drawString(350, y - 20, "Total:")
            c.drawString(450, y - 20, f"${sale.total_amount:,}".replace(",", "."))

            # Profit (Internal use only really, but was in original code)
            # Keeping it to preserve behavior, though usually hidden from customers.
            c.drawString(350, y - 40, "Profit:")
            c.drawString(450, y - 40, f"${sale.total_profit:,}".replace(",", "."))

            c.save()
            logger.info(
                "Receipt saved as PDF", extra={"sale_id": sale.id, "filepath": filepath}
            )
        except Exception as e:
            logger.error(f"Error generating PDF receipt: {str(e)}")
            raise ValidationException(f"Failed to generate PDF: {str(e)}") from e

    def generate_receipt_id(self, sale_date: datetime) -> str:
        """Generate the next receipt ID for the provided sale date."""
        return self._build_receipt_id(sale_date.strftime("%Y-%m-%d"))

    def _build_receipt_id(self, sale_date_str: str) -> str:
        sale_date = datetime.strptime(sale_date_str, "%Y-%m-%d")
        date_part = sale_date.strftime("%y%m%d")
        query = """
            SELECT MAX(CAST(SUBSTR(receipt_id, 7) AS INTEGER)) as last_number
            FROM sales
            WHERE receipt_id LIKE ?
        """
        result = DatabaseManager.fetch_one(query, (f"{date_part}%",))
        last_number = (
            int(result["last_number"]) if result and result["last_number"] else 0
        )
        next_number = last_number + 1
        if next_number > 999:
            raise ValidationException(
                f"Daily receipt limit reached for {sale_date_str} (max 999 per day)"
            )
        return f"{date_part}{next_number:03d}"

    def update_sale_receipt_id(self, sale_id: int, receipt_id: str) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        receipt_id = validate_string(receipt_id, max_length=20)
        query = "UPDATE sales SET receipt_id = ? WHERE id = ?"
        cursor = DatabaseManager.execute_query(query, (receipt_id, sale_id))
        if cursor.rowcount == 0:
            raise NotFoundException(f"Sale with ID {sale_id} not found")
