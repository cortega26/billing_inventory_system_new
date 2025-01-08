from typing import List, Dict, Any, Optional
from database.database_manager import DatabaseManager
from models.sale import Sale, SaleItem
from services.inventory_service import InventoryService
from services.customer_service import CustomerService
from services.product_service import ProductService
from utils.validation.validators import validate_integer, validate_string, validate_date, validate_float
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import ValidationException, DatabaseException, NotFoundException
from utils.system.logger import logger
from utils.system.event_system import event_system
from functools import lru_cache
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


class SaleService:
    def __init__(self):
        self.inventory_service = InventoryService()
        self.customer_service = CustomerService()
        self.product_service = ProductService()

    @staticmethod
    @db_operation(show_dialog=True)
    def diagnose_sales_data():
        query = "SELECT * FROM sales"
        rows = DatabaseManager.fetch_all(query)
        for row in rows:
            print(f"Sale ID: {row['id']}")
            print(f"  customer_id: {row['customer_id']}")
            print(f"  date: {row['date']}")
            print(f"  total_amount: {row['total_amount']}")
            print(f"  total_profit: {row['total_profit']}")
            print(f"  receipt_id: {row['receipt_id']}")
            print("---")

        query = "SELECT * FROM sale_items"
        rows = DatabaseManager.fetch_all(query)
        for row in rows:
            print(f"Sale Item ID: {row['id']}")
            print(f"  sale_id: {row['sale_id']}")
            print(f"  product_id: {row['product_id']}")
            print(f"  quantity: {row['quantity']}")
            print(f"  price: {row['price']}")
            print(f"  profit: {row['profit']}")
            print("---")

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_sale(self, customer_id: int, date: str, items: List[Dict[str, Any]]) -> int:
        """
        1) Insert a new 'sales' row with zero placeholders for total_amount / total_profit.
        2) Insert sale_items for this sale.
        3) Calculate final totals, generate receipt_id, and update 'sales' row.
        4) Emit sale_added event so UI (Sales Tab) refreshes automatically.
        """
        try:
            # If no date was provided, use today's date in "YYYY-MM-DD" format
            sale_date_str = date or datetime.now().strftime("%Y-%m-%d")

            # 1) Create the sale row with placeholders
            insert_query = """
                INSERT INTO sales (customer_id, date, total_amount, total_profit)
                VALUES (?, ?, 0, 0)
            """
            cursor = DatabaseManager.execute_query(insert_query, (customer_id, sale_date_str))
            sale_id = cursor.lastrowid
            if sale_id is None:
                raise DatabaseException("Failed to get new sale ID after insert.")

            # 2) Insert all sale items referencing this sale_id
            items_query = """
                INSERT INTO sale_items (sale_id, product_id, quantity, price, profit)
                VALUES (?, ?, ?, ?, ?)
            """
            # Convert your 'items' list into the parameters needed
            batch_params = []
            for item in items:
                # item might look like:
                # { "product_id": 123, "quantity": 2.0, "sell_price": 1000, "profit": 300 }
                batch_params.append((
                    sale_id,
                    int(item["product_id"]),
                    float(item["quantity"]),
                    int(item["sell_price"]),
                    int(item["profit"])
                ))
            DatabaseManager.executemany(items_query, batch_params)

            # 3) Compute final totals + receipt ID
            total_amount = 0
            total_profit = 0
            for item in items:
                qty = float(item["quantity"])
                unit_price = int(item["sell_price"])
                line_profit = int(item["profit"])
                total_amount += int(round(qty * unit_price))
                total_profit += int(round(qty * line_profit))

            # generate receipt ID from date
            sale_date_obj = datetime.strptime(sale_date_str, "%Y-%m-%d")
            receipt_id = self.generate_receipt_id(sale_date_obj)

            # 4) Update the 'sales' row with correct totals & receipt_id
            update_query = """
                UPDATE sales
                SET total_amount = ?, total_profit = ?, receipt_id = ?
                WHERE id = ?
            """
            DatabaseManager.execute_query(
                update_query,
                (total_amount, total_profit, receipt_id, sale_id)
            )

            # 5) Emit the event => the UI's Sales Tab is presumably listening for this
            event_system.sale_added.emit(sale_id)

            # ***** CLEAR THE CACHED get_all_sales *****
            SaleService.get_all_sales.cache_clear()

            return sale_id

        except Exception as e:
            logger.error(f"Error in create_sale: {str(e)}", extra={"exc_info": True})
            raise DatabaseException(f"Failed to create sale: {str(e)}")


    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_sale(self, sale_id: int) -> Optional[Sale]:
        sale_id = validate_integer(sale_id, min_value=1)
        query = """
        SELECT s.*, 
            COALESCE(s.receipt_id, '') as receipt_id
        FROM sales s
        WHERE s.id = ?
        """
        row = DatabaseManager.fetch_one(query, (sale_id,))
        if row:
            sale = Sale.from_db_row(row)
            sale.items = self.get_sale_items(sale_id)
            logger.info("Sale retrieved", extra={"sale_id": sale_id})
            return sale
        else:
            logger.warning("Sale not found", extra={"sale_id": sale_id})
            raise NotFoundException(f"Sale with ID {sale_id} not found")

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_sales() -> List[Sale]:
        logger.info("Starting get_all_sales method")
        query = """
        SELECT s.*, 
               COALESCE(s.total_amount, 0) as total_amount,
               COALESCE(s.total_profit, 0) as total_profit
        FROM sales s
        ORDER BY s.date DESC
        """
        try:
            rows = DatabaseManager.fetch_all(query)
            logger.info(f"Fetched {len(rows)} rows from database")
        except Exception as e:
            logger.error(f"Error fetching rows: {str(e)}")
            raise

        sales = []
        for row in rows:
            try:
                logger.debug(f"Processing row: {row}")
                sale = Sale.from_db_row(row)
                logger.debug(f"Created Sale object: {sale}")
                sale.items = SaleService.get_sale_items(sale.id)
                logger.debug(f"Fetched items for sale {sale.id}: {len(sale.items)} items")
                sales.append(sale)
            except Exception as e:
                logger.error(f"Error processing sale {row.get('id', 'Unknown')}: {str(e)}")
                logger.error(f"Problematic row data: {row}")

        logger.info(f"All sales retrieved: {len(sales)}")
        return sales

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sale_items(sale_id: int) -> List[SaleItem]:
        logger.debug(f"Fetching items for sale {sale_id}")
        query = """
        SELECT si.*,
               COALESCE(si.quantity, 0) as quantity,
               COALESCE(si.price, 0) as price,
               COALESCE(si.profit, 0) as profit
        FROM sale_items si
        WHERE si.sale_id = ?
        """
        rows = DatabaseManager.fetch_all(query, (sale_id,))
        items = []
        for row in rows:
            try:
                item = SaleItem.from_db_row(row)
                items.append(item)
            except Exception as e:
                logger.error(f"Error processing sale item for sale {sale_id}: {str(e)}")
                logger.error(f"Problematic row data: {row}")
        return items

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_sale(self, sale_id: int) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        items = self.get_sale_items(sale_id)

        self._revert_inventory(items)

        try:
            DatabaseManager.execute_query("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))
            DatabaseManager.execute_query("DELETE FROM sales WHERE id = ?", (sale_id,))
            logger.info("Sale deleted", extra={"sale_id": sale_id})
            event_system.sale_deleted.emit(sale_id)
            self.clear_cache()
        except Exception as e:
            logger.error("Failed to delete sale", extra={"error": str(e), "sale_id": sale_id})
            raise DatabaseException(f"Failed to delete sale: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_sale(self, sale_id: int, customer_id: int, date: str, items: List[Dict[str, Any]]) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        customer_id = validate_integer(customer_id, min_value=1)
        date = validate_date(date)
        self._validate_sale_items(items)

        sale = self.get_sale(sale_id)
        if not sale:
            raise ValidationException(f"Sale with ID {sale_id} not found.")

        sale_datetime = datetime.fromisoformat(sale.date.isoformat())
        if datetime.now() - sale_datetime > timedelta(hours=96):
            raise ValidationException("Sales can only be edited within 96 hours of creation.")

        old_items = self.get_sale_items(sale_id)

        # Revert previous inventory changes
        self._revert_inventory(old_items)

        total_amount = 0
        total_profit = 0
        for item in items:
            product = self.product_service.get_product(item["product_id"])
            if product is None:
                raise ValidationException(f"Product with ID {item['product_id']} not found")
            if product.cost_price is None or product.sell_price is None:
                raise ValidationException(f"Cost/Sell price not set for product '{product.name}'")
            
            item_total = round(item["quantity"] * item["sell_price"])
            item_profit = round(item["quantity"] * (item["sell_price"] - product.cost_price))
            
            total_amount += item_total
            total_profit += item_profit

        self._update_sale(sale_id, customer_id, date, total_amount, total_profit)
        self._update_sale_items(sale_id, items)
        self._update_inventory(items)

        logger.info("Sale updated", extra={"sale_id": sale_id, "customer_id": customer_id})
        event_system.sale_updated.emit(sale_id)
        #self.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_total_sales(start_date: str, end_date: str) -> int:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ?
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        total_sales = int(result["total"] if result else 0)
        logger.info("Total sales retrieved", extra={"start_date": start_date, "end_date": end_date, "total_sales": total_sales})
        return total_sales

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_total_profits(start_date: str, end_date: str) -> int:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT COALESCE(SUM(total_profit), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ?
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        total_profits = int(result["total"] if result else 0)
        logger.info("Total profits retrieved", extra={"start_date": start_date, "end_date": end_date, "total_profits": total_profits})
        return total_profits

    @staticmethod
    def generate_receipt_id(sale_date: datetime) -> str:
        date_part = sale_date.strftime("%y%m%d")
        
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
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def generate_receipt(self, sale_id: int) -> str:
        sale_id = validate_integer(sale_id, min_value=1)
        sale = self.get_sale(sale_id)
        if not sale:
            raise ValidationException(f"Sale with ID {sale_id} not found.")

        if not sale.receipt_id:
            receipt_id = self.generate_receipt_id(sale.date)
            self._update_sale_receipt_id(sale_id, receipt_id)
            sale.receipt_id = receipt_id
        else:
            receipt_id = sale.receipt_id

        logger.info("Receipt generated", extra={"sale_id": sale_id, "receipt_id": receipt_id})
        return receipt_id

    @db_operation(show_dialog=True)
    def _update_sale_receipt_id(self, sale_id: int, receipt_id: str) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        receipt_id = validate_string(receipt_id, max_length=20)
        query = "UPDATE sales SET receipt_id = ? WHERE id = ?"
        DatabaseManager.execute_query(query, (receipt_id, sale_id))

    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def save_receipt_as_pdf(self, sale_id: int, filepath: str) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        filepath = validate_string(filepath, max_length=255)
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
            c.drawString(350, y, f"${item.unit_price:,}".replace(',', '.'))
            c.drawString(450, y, f"${item.total_price():,}".replace(',', '.'))
            y -= 20

        c.drawString(350, y - 20, "Total:")
        c.drawString(450, y - 20, f"${sale.total_amount:,}".replace(',', '.'))

        c.drawString(350, y - 40, "Profit:")
        c.drawString(450, y - 40, f"${sale.total_profit:,}".replace(',', '.'))

        c.save()
        logger.info("Receipt saved as PDF", extra={"sale_id": sale_id, "filepath": filepath})

    @handle_exceptions(DatabaseException, show_dialog=True)
    def send_receipt_via_whatsapp(self, sale_id: int, phone_number: str) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        phone_number = validate_string(phone_number, max_length=20)
        # This is a placeholder. You'll need to implement the actual WhatsApp API integration.
        logger.info("Sending receipt via WhatsApp", extra={"sale_id": sale_id, "phone_number": phone_number})

    def clear_cache(self):
        """Clear the sale cache."""
        SaleService.get_all_sales.cache_clear()
        logger.debug("Sale cache cleared")

    def _validate_sale_items(self, items: List[Dict[str, Any]]) -> None:
        if not items:
            raise ValidationException("Sale must have at least one item")
        for item in items:
            try:
                # Validate quantity as float with 3 decimal places
                quantity = validate_float(float(item["quantity"]), min_value=0.001)
                if round(quantity, 3) != quantity:
                    raise ValidationException("Quantity cannot have more than 3 decimal places")
                
                # Validate price as integer
                sell_price = validate_integer(item["sell_price"], min_value=1)
                if not isinstance(sell_price, int):
                    raise ValidationException("Item sell price must be an integer")
                
            except (ValueError, TypeError):
                raise ValidationException("Invalid quantity or price format")

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        for item in items:
            # Convert float quantity to string for storage
            quantity_str = str(round(float(item["quantity"]), 3))  # Ensure 3 decimal places
            query = """
                INSERT INTO sale_items (sale_id, product_id, quantity, price, profit)
                VALUES (?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(
                query,
                (sale_id, item["product_id"], quantity_str, item["sell_price"], item["profit"])
            )

    def _update_inventory(self, items: List[Dict[str, Any]]) -> None:
        for item in items:
            quantity_change = -abs(float(item["quantity"]))  # Ensure float for quantity
            self.inventory_service.update_quantity(item["product_id"], quantity_change)
            logger.debug(f"Updating inventory for product {item['product_id']}, change: {quantity_change}")

    @staticmethod
    def _revert_inventory(items: List[SaleItem]) -> None:
        for item in items:
            InventoryService.update_quantity(item.product_id, item.quantity)

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale(sale_id: int, customer_id: int, date: str, total_amount: int, total_profit: int) -> None:
        query = "UPDATE sales SET customer_id = ?, date = ?, total_amount = ?, total_profit = ? WHERE id = ?"
        DatabaseManager.execute_query(query, (customer_id, date, total_amount, total_profit, sale_id))

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        DatabaseManager.execute_query("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))
        SaleService._insert_sale_items(sale_id, items)

    @staticmethod
    @db_operation(show_dialog=True)
    def get_top_selling_products(
        start_date: str, end_date: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        limit = validate_integer(limit, min_value=1)
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
        result = DatabaseManager.fetch_all(query, (start_date, end_date, limit))
        logger.info("Top selling products retrieved", extra={"start_date": start_date, "end_date": end_date, "limit": limit, "count": len(result)})
        return result

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_total_sales_by_customer(customer_id: int) -> int:
        customer_id = validate_integer(customer_id, min_value=1)
        query = """
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE customer_id = ?
        """
        result = DatabaseManager.fetch_one(query, (customer_id,))
        total_sales = int(result["total"] if result else 0)
        logger.info("Total sales by customer retrieved", extra={"customer_id": customer_id, "total_sales": total_sales})
        return total_sales

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sales_by_date_range(self, start_date: str, end_date: str) -> List[Sale]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT * FROM sales
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC
        """
        rows = DatabaseManager.fetch_all(query, (start_date, end_date))
        sales = [Sale.from_db_row(row) for row in rows]
        for sale in sales:
            sale.items = self.get_sale_items(sale.id)
        logger.info("Sales by date range retrieved", extra={"start_date": start_date, "end_date": end_date, "count": len(sales)})
        return sales

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_daily_sales_report(self, date: str) -> Dict[str, Any]:
        date = validate_date(date)
        query = """
            SELECT 
                COUNT(*) as total_sales,
                COALESCE(SUM(total_amount), 0) as total_revenue,
                COALESCE(AVG(total_amount), 0) as average_sale_amount,
                COALESCE(SUM(total_profit), 0) as total_profit
            FROM sales
            WHERE date = ?
        """
        result = DatabaseManager.fetch_one(query, (date,))
        report = {
            "date": date,
            "total_sales": 0,
            "total_revenue": 0,
            "average_sale_amount": 0,
            "total_profit": 0
        }
        if result:
            report.update({
                "total_sales": result.get("total_sales", 0),
                "total_revenue": int(result.get("total_revenue", 0)),
                "average_sale_amount": int(result.get("average_sale_amount", 0)),
                "total_profit": int(result.get("total_profit", 0))
            })
        logger.info("Daily sales report generated", extra={"date": date, "report": report})
        return report

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sales_by_product(self, product_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        product_id = validate_integer(product_id, min_value=1)
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT s.date, si.quantity, si.price, si.profit
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE si.product_id = ? AND s.date BETWEEN ? AND ?
            ORDER BY s.date
        """
        rows = DatabaseManager.fetch_all(query, (product_id, start_date, end_date))
        sales = [{"date": row["date"], "quantity": row["quantity"], "price": row["price"], "profit": row["profit"]} for row in rows]
        logger.info("Sales by product retrieved", extra={"product_id": product_id, "start_date": start_date, "end_date": end_date, "count": len(sales)})
        return sales

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sales_distribution_by_category(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT 
                c.name as category_name,
                COUNT(DISTINCT s.id) as sale_count,
                SUM(si.quantity * si.price) as total_revenue,
                SUM(si.profit) as total_profit
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY c.id
            ORDER BY total_revenue DESC
        """
        rows = DatabaseManager.fetch_all(query, (start_date, end_date))
        distribution = [{
            "category_name": row["category_name"] or "Uncategorized", 
            "sale_count": row["sale_count"], 
            "total_revenue": int(row["total_revenue"]),
            "total_profit": int(row["total_profit"])
        } for row in rows]
        logger.info("Sales distribution by category retrieved", extra={"start_date": start_date, "end_date": end_date, "count": len(distribution)})
        return distribution

    @lru_cache(maxsize=100)
    def get_product_details(self, product_id: int) -> Optional[Dict[str, Any]]:
        product = self.product_service.get_product(product_id)
        return product.to_dict() if product else None

    def calculate_total_amount(self, items: List[Dict[str, Any]]) -> int:
        """Calculate total amount for a sale."""
        return sum(int(item['quantity'] * item['sell_price']) for item in items)

    def calculate_total_profit(self, items: List[Dict[str, Any]]) -> int:
        """Calculate total profit for a sale."""
        return sum(int(item['profit']) for item in items)
