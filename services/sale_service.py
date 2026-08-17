from datetime import datetime
from functools import lru_cache
from typing import Any

from database.database_manager import DatabaseManager
from models.enums import MAX_SALE_ITEMS, QUANTITY_PRECISION
from models.sale import Sale, SaleItem
from services.audit_service import AuditService
from services.customer_service import CustomerService
from services.inventory_service import InventoryService
from services.mutation_coordinator import MutationCoordinator
from services.product_service import ProductService
from services.receipt_service import ReceiptService
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, NotFoundException, ValidationException
from utils.helpers import get_product_ids_from_items
from utils.math.financial_calculator import FinancialCalculator
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.validators import (
    validate_date,
    validate_filepath,
    validate_float,
    validate_integer,
    validate_string,
)


def _hydrate_sale_items(sales: list[Sale], sale_ids: list[int | None]) -> None:
    """Batch-load items for the given sales and attach them in place."""
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
    """  # nosec B608
    items_rows = DatabaseManager.fetch_all(items_query, tuple(sale_ids))

    items_by_sale: dict[int, list[SaleItem]] = {}
    for item_row in items_rows:
        sid = item_row["sale_id"]
        if sid not in items_by_sale:
            items_by_sale[sid] = []
        items_by_sale[sid].append(SaleItem.from_db_row(item_row))

    for sale in sales:
        sale.items = items_by_sale.get(sale.id or 0, [])


class SaleService:
    def __init__(self):
        self.inventory_service = InventoryService()
        self.customer_service = CustomerService()
        self.product_service = ProductService()
        self.receipt_service = ReceiptService()

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_sale(
        self, customer_id: int, date: str, items: list[dict[str, Any]]
    ) -> int:
        """
        1) Insert a new 'sales' row with zero placeholders for total_amount / total_profit.
        2) Insert sale_items for this sale.
        3) Calculate final totals, generate receipt_id, and update 'sales' row.
        4) Emit sale_added event so UI (Sales Tab) refreshes automatically.
        """
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
            AuditService.log_operation(
                "create_sale",
                "sale",
                sale_id,
                {
                    "customer_id": customer_id,
                    "date": sale_date_str,
                    "item_count": len(items),
                    "product_ids": get_product_ids_from_items(items),
                    "total_amount": total_amount,
                    "total_profit": total_profit,
                    "receipt_id": receipt_id,
                },
            )

        MutationCoordinator.finalize_mutation(
            entity_id=sale_id,
            items=items,
            signal=event_system.sale_added,
            service_cache_clear_fn=self.clear_cache,
        )

        return sale_id

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sale(self, sale_id: int) -> Sale | None:
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

        logger.warning("Sale not found", extra={"sale_id": sale_id})
        return None

    def _require_sale(self, sale_id: int) -> Sale:
        sale = self.get_sale(sale_id)
        if sale is not None:
            return sale

        raise NotFoundException(f"Sale with ID {sale_id} not found")

    @staticmethod
    @lru_cache(maxsize=128)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_sales(limit: int = 100, offset: int = 0) -> list[Sale]:
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

        sales_rows = DatabaseManager.fetch_all(sales_query, (limit, offset))
        if not sales_rows:
            return []

        sales = [Sale.from_db_row(row) for row in sales_rows]
        sale_ids = [sale.id for sale in sales]

        # Fetch items only for this page's sales — avoids loading the full table
        _hydrate_sale_items(sales, sale_ids)

        logger.info(
            f"Retrieved {len(sales)} sales",
            extra={"limit": limit, "offset": offset},
        )
        return sales

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sale_items(sale_id: int) -> list[SaleItem]:
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
        sale = self._require_sale(sale_id)
        if sale.status == "cancelled":
            raise ValidationException(f"Sale {sale_id} is already cancelled")
        items = sale.items

        with DatabaseManager.transaction():
            InventoryService.apply_batch_updates(
                items, multiplier=1.0, emit_events=False
            )
            AuditService.log_operation(
                "delete_sale",
                "sale",
                sale_id,
                {
                    "item_count": len(items),
                    "product_ids": get_product_ids_from_items(items),
                },
            )
            DatabaseManager.execute_query(
                "DELETE FROM sale_items WHERE sale_id = ?", (sale_id,)
            )
            DatabaseManager.execute_query(
                "DELETE FROM sales WHERE id = ?", (sale_id,)
            )
        logger.info("Sale deleted", extra={"sale_id": sale_id})
        MutationCoordinator.finalize_mutation(
            entity_id=sale_id,
            items=items,
            signal=event_system.sale_deleted,
            service_cache_clear_fn=self.clear_cache,
        )

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def cancel_sale(self, sale_id: int) -> None:
        """
        Cancel a sale by setting status='cancelled' and reverting stock.

        Unlike delete_sale, the sale record is preserved for audit purposes.
        Raises ValidationException if the sale is already cancelled.
        """
        sale_id = validate_integer(sale_id, min_value=1)
        sale = self._require_sale(sale_id)
        if sale.status == "cancelled":
            raise ValidationException(f"Sale {sale_id} is already cancelled")

        items = sale.items

        with DatabaseManager.transaction():
            InventoryService.apply_batch_updates(
                items, multiplier=1.0, emit_events=False
            )
            DatabaseManager.execute_query(
                "UPDATE sales SET status = 'cancelled' WHERE id = ?", (sale_id,)
            )
            AuditService.log_operation(
                "cancel_sale",
                "sale",
                sale_id,
                {
                    "item_count": len(items),
                    "product_ids": get_product_ids_from_items(items),
                },
            )
        logger.info("Sale cancelled", extra={"sale_id": sale_id})
        MutationCoordinator.finalize_mutation(
            entity_id=sale_id,
            items=items,
            signal=event_system.sale_updated,
            service_cache_clear_fn=self.clear_cache,
        )

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_sale(
        self, sale_id: int, customer_id: int, date: str, items: list[dict[str, Any]]
    ) -> None:
        from services.update_sale_workflow import UpdateSaleWorkflow

        UpdateSaleWorkflow(self).execute(sale_id, customer_id, date, items)

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_total_sales(start_date: str, end_date: str) -> int:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ? AND status = 'confirmed'
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
    def get_total_units_sold(start_date: str, end_date: str) -> float:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT COALESCE(ROUND(SUM(si.quantity), 3), 0) as total_units
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE s.date BETWEEN ? AND ? AND s.status = 'confirmed'
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        total_units = float(result["total_units"] if result else 0)
        logger.info(
            "Total units sold retrieved",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "total_units": total_units,
            },
        )
        return total_units

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_total_profits(start_date: str, end_date: str) -> int:
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT COALESCE(SUM(total_profit), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ? AND status = 'confirmed'
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
        sale = self._require_sale(sale_id)

        if not sale.receipt_id:
            if sale.date is None:
                raise ValidationException("Sale date is required to generate receipt")
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
        cursor = DatabaseManager.execute_query(query, (receipt_id, sale_id))
        if cursor.rowcount == 0:
            raise NotFoundException(f"Sale with ID {sale_id} not found")

    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def save_receipt_as_pdf(self, sale_id: int, filepath: str) -> None:
        sale_id = validate_integer(sale_id, min_value=1)
        filepath = validate_filepath(filepath)

        sale = self._require_sale(sale_id)

        items = self.get_sale_items(sale_id)

        # Delegate to ReceiptService
        self.receipt_service.generate_pdf(sale, items, filepath)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the sale cache."""
        SaleService.get_all_sales.cache_clear()
        logger.debug("Sale cache cleared")

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
        next_number = last_number + 1
        if next_number > 999:
            raise ValidationException(
                f"Daily receipt limit reached for {sale_date_str} (max 999 per day)"
            )
        return f"{date_part}{next_number:03d}"

    def _validate_sale_items(self, items: list[dict[str, Any]]) -> None:
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
                raise ValidationException("Invalid quantity or price format") from None

    @staticmethod
    @db_operation(show_dialog=True)
    def _insert_sale_items(sale_id: int, items: list[dict[str, Any]]) -> None:
        for item in items:
            # Store quantity as a number (not a string) for consistent typing
            quantity = round(float(item["quantity"]), QUANTITY_PRECISION)
            query = """
                INSERT INTO sale_items (sale_id, product_id, quantity, price, profit)
                VALUES (?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(
                query,
                (
                    sale_id,
                    item["product_id"],
                    quantity,
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
    def _update_sale_items(sale_id: int, items: list[dict[str, Any]]) -> None:
        DatabaseManager.execute_query(
            "DELETE FROM sale_items WHERE sale_id = ?", (sale_id,)
        )
        SaleService._insert_sale_items(sale_id, items)

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_sales_by_date_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Sale]:
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
        _hydrate_sale_items(sales, sale_ids)

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
    def get_sale_statistics(self, start_date: str, end_date: str) -> dict[str, Any]:
        """Get aggregated sale statistics for a date range."""
        start_date = validate_date(start_date)
        end_date = validate_date(end_date)
        query = """
            SELECT
                COUNT(*) as total_sales,
                SUM(total_amount) as total_amount,
                SUM(total_profit) as total_profit
            FROM sales
            WHERE date BETWEEN ? AND ? AND status = 'confirmed'
        """
        result = DatabaseManager.fetch_one(query, (start_date, end_date))

        if result:
            return {
                "total_sales": result["total_sales"] or 0,
                "total_amount": result["total_amount"] or 0,
                "total_profit": result["total_profit"] or 0,
            }
        return {"total_sales": 0, "total_amount": 0, "total_profit": 0}
