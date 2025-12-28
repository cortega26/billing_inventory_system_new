from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from typing import Optional

from models.sale import Sale
from services.customer_service import CustomerService
from utils.system.logger import logger
from utils.validation.validators import validate_integer, validate_string
from utils.exceptions import ValidationException

class ReceiptService:
    def __init__(self):
        # We might need customer service if we want to fetch customer details inside receipt generation,
        # but Sale object passed usually has what we need or we pass the data.
        # For now, let's keep it simple.
        pass

    def generate_pdf(self, sale: Sale, items: list, filepath: str) -> None:
        """
        Generate a PDF receipt for a sale.
        
        Args:
            sale: The Sale object (with customer_id, receipt_id, dates, totals).
            items: List of SaleItem objects.
            filepath: Destination path for the PDF.
        """
        filepath = validate_string(filepath, max_length=255)
        
        try:
            c = canvas.Canvas(filepath, pagesize=letter)
            width, height = letter

            # Set up the document
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, f"Receipt #{sale.receipt_id}")

            c.setFont("Helvetica", 12)
            c.drawString(50, height - 80, f"Date: {sale.date.strftime('%Y-%m-%d')}")
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
                p_name = item.product_name if hasattr(item, 'product_name') and item.product_name else f"Product ID: {item.product_id}"
                
                c.drawString(50, y, p_name)
                c.drawString(250, y, str(item.quantity))
                c.drawString(350, y, f"${item.unit_price:,}".replace(",", "."))
                
                # item.total_price() is a method on SaleItem usually
                total_line = item.total_price() if hasattr(item, 'total_price') else int(item.quantity * item.unit_price)
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
            raise ValidationException(f"Failed to generate PDF: {str(e)}")

    def send_via_whatsapp(self, sale_id: int, phone_number: str) -> None:
        """
        Send receipt via WhatsApp (Placeholder).
        """
        sale_id = validate_integer(sale_id, min_value=1)
        phone_number = validate_string(phone_number, max_length=20)
        
        # This is a placeholder. You'll need to implement the actual WhatsApp API integration.
        logger.info(
            "Sending receipt via WhatsApp",
            extra={"sale_id": sale_id, "phone_number": phone_number},
        )
