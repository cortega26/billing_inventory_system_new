from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

from database.database_manager import DatabaseManager
from models.enums import MAX_SALE_ITEMS, QUANTITY_PRECISION
from models.sale import Sale, SaleItem
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.receipt_service import ReceiptService
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, NotFoundException, ValidationException
from utils.math.financial_calculator import FinancialCalculator
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.validators import (
    validate_date,
    validate_float,
    validate_integer,
    validate_string,
)


class SaleService:
    def __init__(self):
        self.inventory_service = InventoryService()
        self.customer_service = CustomerService()
        self.product_service = ProductService()
        self.receipt_service = ReceiptService()

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_sale(
        self, customer_id: int, date: str, items: List[Dict[str, Any]]
    ) -> int:
        """
        1) Insert a new 'sales' row with zero placeholders for total_amount / total_profit.
        2) Insert sale_items for this sale.
        3) Calculate final totals, generate receipt_id, and update 'sales' row.
        4) Emit sale_added event so UI (Sales Tab) refreshes automatically.
        """
        try:
            customer_id = validate_integer(customer_id, min_value=1)
            sale_date_str = (
                validate_date(date) if date else datetime.now().strftime("%Y-%m-%d")
            )
            self._validate_sale_items(items)

            total_amount = sum(
                FinancialCalculator.calculate_item_total(
                    item["quantity"], item["sell_price"]
                )
                for item in items
            )
            total_profit = sum(int(item["profit"]) for item in items)

            with DatabaseManager.transaction():
                insert_query = """
                    INSERT INTO sales (customer_id, date, total_amount, total_profit)
                    VALUES (?, ?, 0, 0)
                """
                cursor = DatabaseManager.execute_query(
                    insert_query, (customer_id, sale_date_str)
                )
                sale_id = cursor.lastrowid
                if sale_id is None:
                    raise DatabaseException("Failed to get new sale ID after insert.")

                items_query = """
                    INSERT INTO sale_items (sale_id, product_id, quantity, price, profit)
                    VALUES (?, ?, ?, ?, ?)
                """
                batch_params = [
                    (
                        sale_id,
                        int(item["product_id"]),
                        float(item["quantity"]),
                        int(item["sell_price"]),
                        int(item["profit"]),
                    )
                    for item in items
                ]
                DatabaseManager.executemany(items_query, batch_params)

                receipt_id = self._build_receipt_id(sale_date_str)
                update_query = """
                    UPDATE sales
                    SET total_amount = ?, total_profit = ?, receipt_id = ?
                    WHERE id = ?
                """
                DatabaseManager.execute_query(
                    update_query, (total_amount, total_profit, receipt_id, sale_id)
                )

                InventoryService.apply_batch_updates(
                    items, multiplier=-1.0, emit_events=False
                )

            self._finalize_sale_mutation(sale_id, items, event_system.sale_added)

            return sale_id

        except Exception as e:
            if isinstance(e, (ValidationException, NotFoundException)):
                raise e
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

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_customer_sales(self, customer_id: int) -> List[Sale]:
        """Get all sales for a specific customer."""
        customer_id = validate_integer(customer_id, min_value=1)
        query = "SELECT * FROM sales WHERE customer_id = ?"
        rows = DatabaseManager.fetch_all(query, (customer_id,))
        sales = []
        for row in rows:
            sale = Sale.from_db_row(row)
            sale.items = self.get_sale_items(sale.id)
            sales.append(sale)
        logger.info(
            "Customer sales retrieved",
            extra={"customer_id": customer_id, "count": len(sales)},
        )
        return sales

    @staticmethod
    @lru_cache(maxsize=128)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_sales(limit: int = 100, offset: int = 0) -> List[Sale]:
        """Get a page of sales with items in optimized queries.

        Args:
            limit: Maximum number of sales to return (default 100).
            offset: Number of sales to skip for pagination (default 0).
        """
        limit = validate_integer(limit, min_value=1)
        offset = validate_integer(offset, min_value=0)

        sales_query = """
            SELECT s.*,
                COALESCE(s.total_amount, 0) as total_amount,
                COALESCE(s.total_profit, 0) as total_profit
            FROM sales s
            ORDER BY s.date DESC
            LIMIT ? OFFSET ?
        """

        try:
            sales_rows = DatabaseManager.fetch_all(sales_query, (limit, offset))
            if not sales_rows:
                return []

            sales = [Sale.from_db_row(row) for row in sales_rows]
            sale_ids = [sale.id for sale in sales]

            # Fetch items only for this page's sales — avoids loading the full table
            placeholders = ",".join("?" * len(sale_ids))
            items_query = f"""
                SELECT si.*,
                    p.name as product_name,
                    COALESCE(si.quantity, 0) as quantity,
                    COALESCE(si.price, 0) as price,
                    COALESCE(si.profit, 0) as profit
                FROM sale_items si
                LEFT JOIN products p ON si.product_id = p.id
                WHERE si.sale_id IN ({placeholders})
                ORDER BY si.sale_id, si.id
            """
            items_rows = DatabaseManager.fetch_all(items_query, tuple(sale_ids))

            items_by_sale: Dict[int, List[SaleItem]] = {}
            for item_row in items_rows:
                sid = item_row["sale_id"]
                if sid not in items_by_sale:
                    items_by_sale[sid] = []
                items_by_sale[sid].append(SaleItem.from_db_row(item_row))

            for sale in sales:
                sale.items = items_by_sale.get(sale.id, [])

            logger.info(
                f"Retrieved {len(sales)} sales",
                extra={"limit": limit, "offset": offset},
            )
            return sales

        except Exception as e:
            logger.error(f"Error fetching sales: {str(e)}")
            raise DatabaseException(f"Failed to fetch sales: {str(e)}")

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
            item = SaleItem.from_db_row(row)
            items.append(item)
        return items

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_sale(self, sale_id: int) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        items = self.get_sale_items(sale_id)

        try:
            with DatabaseManager.transaction():
                InventoryService.apply_batch_updates(
                    items, multiplier=1.0, emit_events=False
                )
                DatabaseManager.execute_query(
                    "DELETE FROM sale_items WHERE sale_id = ?", (sale_id,)
                )
                DatabaseManager.execute_query(
                    "DELETE FROM sales WHERE id = ?", (sale_id,)
                )
            logger.info("Sale deleted", extra={"sale_id": sale_id})
            self._finalize_sale_mutation(sale_id, items, event_system.sale_deleted)
        except Exception as e:
            logger.error(
                "Failed to delete sale", extra={"error": str(e), "sale_id": sale_id}
            )
            raise DatabaseException(f"Failed to delete sale: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def cancel_sale(self, sale_id: int) -> None:
        """
        Cancel a sale by setting status='cancelled' and reverting stock.

        Unlike delete_sale, the sale record is preserved for audit purposes.
        Raises ValidationException if the sale is already cancelled.
        """
        sale_id = validate_integer(sale_id, min_value=1)
        sale = self.get_sale(sale_id)
        if not sale:
            raise NotFoundException(f"Sale with ID {sale_id} not found")
        if sale.status == "cancelled":
            raise ValidationException(f"Sale {sale_id} is already cancelled")

        items = self.get_sale_items(sale_id)

        try:
            with DatabaseManager.transaction():
                InventoryService.apply_batch_updates(
                    items, multiplier=1.0, emit_events=False
                )
                DatabaseManager.execute_query(
                    "UPDATE sales SET status = 'cancelled' WHERE id = ?", (sale_id,)
                )
            logger.info("Sale cancelled", extra={"sale_id": sale_id})
            self._finalize_sale_mutation(sale_id, items, event_system.sale_updated)
        except Exception as e:
            logger.error(
                "Failed to cancel sale", extra={"error": str(e), "sale_id": sale_id}
            )
            raise DatabaseException(f"Failed to cancel sale: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_sale(
        self, sale_id: int, customer_id: int, date: str, items: List[Dict[str, Any]]
    ) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        customer_id = validate_integer(customer_id, min_value=1)
        date = validate_date(date)
        self._validate_sale_items(items)

        sale = self.get_sale(sale_id)
        if not sale:
            raise ValidationException(f"Sale with ID {sale_id} not found.")

        old_items = self.get_sale_items(sale_id)

        # item["profit"] was computed server-side by _validate_sale_items above
        total_amount = sum(
            FinancialCalculator.calculate_item_total(item["quantity"], item["sell_price"])
            for item in items
        )
        total_profit = sum(item["profit"] for item in items)

        with DatabaseManager.transaction():
            InventoryService.apply_batch_updates(
                old_items, multiplier=1.0, emit_events=False
            )
            self._update_sale(sale_id, customer_id, date, total_amount, total_profit)
            self._update_sale_items(sale_id, items)
            InventoryService.apply_batch_updates(
                items, multiplier=-1.0, emit_events=False
            )

        logger.info(
            "Sale updated", extra={"sale_id": sale_id, "customer_id": customer_id}
        )
        self._finalize_sale_mutation(
            sale_id, [*old_items, *items], event_system.sale_updated
        )

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
        logger.info(
            "Total sales retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "total_sales": total_sales,
            },
        )
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
        logger.info(
            "Total profits retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "total_profits": total_profits,
            },
        )
        return total_profits

    @staticmethod
    def generate_receipt_id(sale_date: datetime) -> str:
        """Generate the next receipt ID for the provided sale date."""
        return SaleService._build_receipt_id(sale_date.strftime("%Y-%m-%d"))

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

        logger.info(
            "Receipt generated", extra={"sale_id": sale_id, "receipt_id": receipt_id}
        )
        return receipt_id

    @db_operation(show_dialog=True)
    def _update_sale_receipt_id(self, sale_id: int, receipt_id: str) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        receipt_id = validate_string(receipt_id, max_length=20)
        query = "UPDATE sales SET receipt_id = ? WHERE id = ?"
        DatabaseManager.execute_query(query, (receipt_id, sale_id))

    @db_operation(show_dialog=True)
    def update_sale_receipt(self, sale_id: int, receipt_id: str) -> None:
        """Public method to update sale receipt ID."""
        self._update_sale_receipt_id(sale_id, receipt_id)

    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def save_receipt_as_pdf(self, sale_id: int, filepath: str) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        filepath = validate_string(filepath, max_length=255)

        sale = self.get_sale(sale_id)
        if not sale:
            raise ValidationException(f"Sale with ID {sale_id} not found.")

        items = self.get_sale_items(sale_id)

        # Delegate to ReceiptService
        self.receipt_service.generate_pdf(sale, items, filepath)

    @handle_exceptions(DatabaseException, show_dialog=True)
    def send_receipt_via_whatsapp(self, sale_id: int, phone_number: str) -> None:
        self.receipt_service.send_via_whatsapp(sale_id, phone_number)

    def clear_cache(self):
        """Clear the sale cache."""
        SaleService.get_all_sales.cache_clear()
        logger.debug("Sale cache cleared")

    def _finalize_sale_mutation(
        self, sale_id: int, items: List[Any], signal: Any
    ) -> None:
        """Refresh caches and emit post-commit events for sale mutations."""
        InventoryService.clear_cache()
        for product_id in self._get_product_ids(items):
            event_system.inventory_changed.emit(product_id)
        self.clear_cache()
        signal.emit(sale_id)

    @staticmethod
    def _build_receipt_id(sale_date_str: str) -> str:
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
        return f"{date_part}{last_number + 1:03d}"

    @staticmethod
    def _get_product_ids(items: List[Any]) -> List[int]:
        product_ids: List[int] = []
        for item in items:
            product_id = (
                item["product_id"]
                if isinstance(item, dict)
                else getattr(item, "product_id", None)
            )
            if product_id is not None and product_id not in product_ids:
                product_ids.append(int(product_id))
        return product_ids

    def _validate_sale_items(self, items: List[Dict[str, Any]]) -> None:
        if not items:
            raise ValidationException("Sale must have at least one item")
        if len(items) > MAX_SALE_ITEMS:
            raise ValidationException(
                f"Too many items in single sale (max {MAX_SALE_ITEMS})"
            )
        for item in items:
            try:
                # Validate quantity as float with precision
                quantity = validate_float(float(item["quantity"]), min_value=0.001)
                if round(quantity, QUANTITY_PRECISION) != quantity:
                    raise ValidationException(
                        f"Quantity cannot have more than {QUANTITY_PRECISION} decimal places"
                    )

                # Validate price as integer
                sell_price = validate_integer(item["sell_price"], min_value=1)
                if not isinstance(sell_price, int):
                    raise ValidationException("Item sell price must be an integer")

                # Compute profit server-side; ignore any client-supplied value
                product = self.product_service.get_product(item["product_id"])
                if product is None:
                    raise ValidationException(
                        f"Product with ID {item['product_id']} not found"
                    )
                item["profit"] = FinancialCalculator.calculate_item_profit(
                    quantity, sell_price, product.cost_price
                )

            except (ValueError, TypeError):
                raise ValidationException("Invalid quantity or price format")

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        for item in items:
            # Convert float quantity to string for storage
            # Ensure precision decimal places
            quantity_str = str(round(float(item["quantity"]), QUANTITY_PRECISION))
            query = """
                INSERT INTO sale_items (sale_id, product_id, quantity, price, profit)
                VALUES (?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(
                query,
                (
                    sale_id,
                    item["product_id"],
                    quantity_str,
                    item["sell_price"],
                    item["profit"],
                ),
            )

    # _update_inventory and _revert_inventory removed in favor of InventoryService.apply_batch_updates

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale(
        sale_id: int, customer_id: int, date: str, total_amount: int, total_profit: int
    ) -> None:
        query = "UPDATE sales SET customer_id = ?, date = ?, total_amount = ?, total_profit = ? WHERE id = ?"
        DatabaseManager.execute_query(
            query, (customer_id, date, total_amount, total_profit, sale_id)
        )

    @staticmethod
    @db_operation(show_dialog=True)
    def _update_sale_items(sale_id: int, items: List[Dict[str, Any]]) -> None:
        DatabaseManager.execute_query(
            "DELETE FROM sale_items WHERE sale_id = ?", (sale_id,)
        )
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
        logger.info(
            "Top selling products retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "count": len(result),
            },
        )
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
        logger.info(
            "Total sales by customer retrieved",
            extra={"customer_id": customer_id, "total_sales": total_sales},
        )
        return total_sales

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sales_by_date_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Sale]:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        limit = validate_integer(limit, min_value=1)
        offset = validate_integer(offset, min_value=0)

        query = """
            SELECT * FROM sales
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        """
        rows = DatabaseManager.fetch_all(query, (start_date, end_date, limit, offset))
        if not rows:
            return []

        sales = [Sale.from_db_row(row) for row in rows]
        sale_ids = [sale.id for sale in sales]

        # Batch-load items for this page — eliminates N+1
        placeholders = ",".join("?" * len(sale_ids))
        items_query = f"""
            SELECT si.*,
                p.name as product_name,
                COALESCE(si.quantity, 0) as quantity,
                COALESCE(si.price, 0) as price,
                COALESCE(si.profit, 0) as profit
            FROM sale_items si
            LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id IN ({placeholders})
            ORDER BY si.sale_id, si.id
        """
        items_rows = DatabaseManager.fetch_all(items_query, tuple(sale_ids))

        items_by_sale: Dict[int, List[SaleItem]] = {}
        for item_row in items_rows:
            sid = item_row["sale_id"]
            if sid not in items_by_sale:
                items_by_sale[sid] = []
            items_by_sale[sid].append(SaleItem.from_db_row(item_row))

        for sale in sales:
            sale.items = items_by_sale.get(sale.id, [])

        logger.info(
            "Sales by date range retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "offset": offset,
                "count": len(sales),
            },
        )
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
            "total_profit": 0,
        }
        if result:
            report.update(
                {
                    "total_sales": result.get("total_sales", 0),
                    "total_revenue": int(result.get("total_revenue", 0)),
                    "average_sale_amount": int(result.get("average_sale_amount", 0)),
                    "total_profit": int(result.get("total_profit", 0)),
                }
            )
        logger.info(
            "Daily sales report generated", extra={"date": date, "report": report}
        )
        return report

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sales_by_product(
        self, product_id: int, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
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
        sales = [
            {
                "date": row["date"],
                "quantity": row["quantity"],
                "price": row["price"],
                "profit": row["profit"],
            }
            for row in rows
        ]
        logger.info(
            "Sales by product retrieved",
            extra={
                "product_id": product_id,
                "start_date": start_date,
                "end_date": end_date,
                "count": len(sales),
            },
        )
        return sales

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sales_distribution_by_category(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
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
        distribution = [
            {
                "category_name": row["category_name"] or "Uncategorized",
                "sale_count": row["sale_count"],
                "total_revenue": int(row["total_revenue"]),
                "total_profit": int(row["total_profit"]),
            }
            for row in rows
        ]
        logger.info(
            "Sales distribution by category retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "count": len(distribution),
            },
        )
        return distribution

    @lru_cache(maxsize=100)
    def get_product_details(self, product_id: int) -> Optional[Dict[str, Any]]:
        product = self.product_service.get_product(product_id)
        return product.to_dict() if product else None

    def calculate_total_amount(self, items: List[Dict[str, Any]]) -> int:
        """Calculate total amount for a sale."""
        return sum(
            FinancialCalculator.calculate_item_total(
                item["quantity"], item["sell_price"]
            )
            for item in items
        )

    def calculate_total_profit(self, items: List[Dict[str, Any]]) -> int:
        """Calculate total profit for a sale."""
        return sum(int(item["profit"]) for item in items)

    def get_sale_statistics(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get aggregated sale statistics for a date range."""
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT 
                COUNT(*) as total_sales,
                SUM(total_amount) as total_amount,
                SUM(total_profit) as total_profit
            FROM sales 
            WHERE date BETWEEN ? AND ?
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))

        if result:
            return {
                "total_sales": result["total_sales"] or 0,
                "total_amount": result["total_amount"] or 0,
                "total_profit": result["total_profit"] or 0,
            }
        return {"total_sales": 0, "total_amount": 0, "total_profit": 0}
