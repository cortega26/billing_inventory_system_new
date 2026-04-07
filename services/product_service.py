from functools import lru_cache
from typing import Any, Dict, List, Optional

from database.database_manager import DatabaseManager
from models.product import Product
from services.audit_service import AuditService
from services.product_service_support import (
    build_product_update_statement,
    normalize_create_product_data,
    validate_barcode_field,
    validate_category_field,
    validate_description_field,
    validate_money_field,
    validate_name_field,
)
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import (
    DatabaseException,
    NotFoundException,
    ValidationException,
)
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.validators import validate_integer, validate_string


class ProductService:
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_product(self, product_data: Dict[str, Any]) -> Optional[int]:
        validated_data = normalize_create_product_data(
            self._validate_product_data(product_data, is_create=True)
        )

        try:
            with DatabaseManager.transaction():
                product_id = self._insert_product_with_inventory(validated_data)
                self._log_product_creation(product_id, validated_data)

            self._finalize_product_creation(product_id, validated_data["name"])

            return product_id

        except Exception as e:
            logger.error(
                "Failed to create product",
                extra={"error": str(e), "data": validated_data},
            )
            if isinstance(e, (ValidationException, DatabaseException)):
                raise
            raise DatabaseException(f"Failed to create product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_product(self, product_id: int) -> Optional[Product]:
        """
        Get a product by ID.

        Args:
            product_id: The product ID.

        Returns:
            Optional[Product]: The product if found, otherwise None.

        Raises:
            DatabaseException: If database operation fails.
        """
        product_id = validate_integer(product_id, min_value=1)
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = :product_id
        """
        row = DatabaseManager.fetch_one(query, {"product_id": product_id})
        if row:
            logger.info("Product retrieved", extra={"product_id": product_id})
            return Product.from_db_row(row)

        logger.warning("Product not found", extra={"product_id": product_id})
        return None

    def _require_product(self, product_id: int) -> Product:
        product = self.get_product(product_id)
        if product is not None:
            return product

        raise NotFoundException(f"Product with ID {product_id} not found")

    @lru_cache(maxsize=4)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_products(self, active_only: bool = True) -> List[Product]:
        """Get products, optionally including archived records."""
        query = """
        SELECT DISTINCT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE (? = 0 OR p.is_active = 1)
        ORDER BY p.id
        """
        try:
            rows = DatabaseManager.fetch_all(query, (1 if active_only else 0,))
            products = [Product.from_db_row(row) for row in rows]
            logger.info(
                "Products retrieved",
                extra={"count": len(products), "active_only": active_only},
            )
            return products
        except Exception as e:
            logger.error(f"Error retrieving products: {str(e)}")
            raise DatabaseException(f"Failed to retrieve products: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(
        NotFoundException, ValidationException, DatabaseException, show_dialog=True
    )
    def update_product(self, product_id: int, update_data: Dict[str, Any]) -> None:
        """
        Update a product.

        Args:
            product_id: The product ID.
            update_data: Dictionary containing fields to update.

        Raises:
            NotFoundException: If product not found.
            ValidationException: If validation fails.
            DatabaseException: If database operation fails.
        """
        product_id = validate_integer(product_id, min_value=1)
        current_product = self._require_product(product_id)
        self._validate_changed_barcode(current_product, update_data)
        validated_data = self._validate_product_data(update_data, is_create=False)

        if not validated_data:
            logger.warning(
                "No valid fields to update", extra={"product_id": product_id}
            )
            return

        query, params, updated_fields = build_product_update_statement(
            product_id, validated_data
        )

        try:
            with DatabaseManager.transaction():
                DatabaseManager.execute_query(query, params)
                AuditService.log_operation(
                    "update_product",
                    "product",
                    product_id,
                    {"updated_fields": updated_fields},
                )
            self._finalize_product_update(product_id, updated_fields)
        except Exception as e:
            logger.error(
                "Failed to update product",
                extra={"error": str(e), "product_id": product_id},
            )
            raise DatabaseException(f"Failed to update product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_product(self, product_id: int) -> None:
        """Archive a product instead of hard-deleting ledger references."""
        product_id = validate_integer(product_id, min_value=1)

        try:
            with DatabaseManager.transaction():
                cursor = DatabaseManager.execute_query(
                    """
                    UPDATE products
                    SET is_active = 0,
                        deleted_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (product_id,),
                )
                if cursor.rowcount == 0:
                    raise NotFoundException(f"Product with ID {product_id} not found")
                AuditService.log_operation(
                    "delete_product",
                    "product",
                    product_id,
                    {"mode": "archive"},
                )

            self.clear_cache()
            event_system.product_deleted.emit(product_id)
            logger.info("Product archived", extra={"product_id": product_id})

        except Exception as e:
            logger.error(
                "Failed to archive product",
                extra={"error": str(e), "product_id": product_id},
            )
            if isinstance(e, NotFoundException):
                raise
            raise DatabaseException(f"Failed to archive product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def restore_product(self, product_id: int) -> None:
        """Restore an archived product."""
        product_id = validate_integer(product_id, min_value=1)
        try:
            with DatabaseManager.transaction():
                cursor = DatabaseManager.execute_query(
                    """
                    UPDATE products
                    SET is_active = 1,
                        deleted_at = NULL
                    WHERE id = ?
                    """,
                    (product_id,),
                )
                if cursor.rowcount == 0:
                    raise NotFoundException(f"Product with ID {product_id} not found")
                AuditService.log_operation(
                    "restore_product",
                    "product",
                    product_id,
                    None,
                )

            self.clear_cache()
            event_system.product_updated.emit(product_id)
            logger.info("Product restored", extra={"product_id": product_id})
        except Exception as e:
            logger.error(
                "Failed to restore product",
                extra={"error": str(e), "product_id": product_id},
            )
            if isinstance(e, NotFoundException):
                raise
            raise DatabaseException(f"Failed to restore product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_products(self, search_term: str, active_only: bool = True) -> List[Product]:
        """
        Search products by name, description, or barcode.

        Args:
            search_term: The search term.

        Returns:
            List[Product]: List of matching products.

        Raises:
            DatabaseException: If database operation fails.
        """
        search_term = validate_string(search_term, max_length=100)
        query = """
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE (
            LOWER(p.name) LIKE LOWER(:search_pattern)
            OR LOWER(COALESCE(p.description, '')) LIKE LOWER(:search_pattern)
            OR LOWER(COALESCE(p.barcode, '')) LIKE LOWER(:search_pattern)
        )
        AND (:active_only = 0 OR p.is_active = 1)
        ORDER BY p.name
        """
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(
            query,
            {"search_pattern": search_pattern, "active_only": 1 if active_only else 0},
        )
        products = [Product.from_db_row(row) for row in rows]
        logger.info(
            "Products searched",
            extra={"search_term": search_term, "count": len(products)},
        )
        return products

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_product_by_barcode(
        self, barcode: str, active_only: bool = True
    ) -> Optional[Product]:
        """Get a product by barcode."""
        logger.debug(f"Getting product by barcode: {barcode}")
        query = """
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.barcode = ?
              AND (? = 0 OR p.is_active = 1)
        """
        try:
            row = DatabaseManager.fetch_one(query, (barcode, 1 if active_only else 0))
            if row:
                logger.debug(f"Found product row: {row}")
                product = Product.from_db_row(row)
                logger.debug(f"Created product object: {vars(product)}")
                return product
            return None
        except Exception as e:
            logger.error(f"Error getting product by barcode: {str(e)}")
            raise DatabaseException(f"Failed to get product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_product_profit_margin(self, product_id: int) -> int:
        """
        Calculate product profit margin.

        Args:
            product_id: The product ID.

        Returns:
            int: The profit margin percentage.

        Raises:
            NotFoundException: If product not found.
            DatabaseException: If database operation fails.
        """
        try:
            product = self._require_product(product_id)

            if product.cost_price is None or product.sell_price is None:
                logger.info(
                    f"Unable to calculate profit margin for product {product_id}: cost_price or sell_price is None"
                )
                return 0

            if product.sell_price == 0:
                logger.warning(
                    f"Sell price is zero for product {product_id}, unable to calculate profit margin"
                )
                return 0

            profit_margin = int(
                (product.sell_price - product.cost_price) / product.sell_price * 100
            )
            logger.info(
                f"Calculated profit margin for product {product_id}: {profit_margin}%"
            )
            return profit_margin
        except Exception as e:
            logger.error(
                f"Error calculating profit margin for product {product_id}: {str(e)}"
            )
            raise

    def clear_cache(self):
        """Clear the product cache."""
        self.get_all_products.cache_clear()
        logger.debug("Product cache cleared")

    @staticmethod
    def _insert_product_with_inventory(validated_data: Dict[str, Any]) -> int:
        query = """
        INSERT INTO products (
            name, description, category_id, cost_price, sell_price, barcode
        ) VALUES (
            :name, :description, :category_id, :cost_price, :sell_price, :barcode
        )
        """
        cursor = DatabaseManager.execute_query(query, validated_data)
        product_id = cursor.lastrowid
        if not product_id:
            raise DatabaseException("Failed to create product: No product ID returned")

        DatabaseManager.execute_query(
            """
            INSERT INTO inventory (product_id, quantity)
            VALUES (?, 0.000)
            """,
            (product_id,),
        )
        return product_id

    @staticmethod
    def _log_product_creation(product_id: int, validated_data: Dict[str, Any]) -> None:
        AuditService.log_operation(
            "create_product",
            "product",
            product_id,
            {
                "name": validated_data["name"],
                "category_id": validated_data.get("category_id"),
                "sell_price": validated_data.get("sell_price"),
                "cost_price": validated_data.get("cost_price"),
            },
        )

    def _finalize_product_creation(self, product_id: int, product_name: str) -> None:
        self.clear_cache()
        logger.info(
            "Product created with inventory initialized",
            extra={"product_id": product_id, "name": product_name},
        )
        try:
            event_system.product_added.emit(product_id)
            event_system.inventory_changed.emit(product_id)
        except Exception as e:
            logger.warning(f"Failed to emit events for product creation: {e}")

    def _validate_changed_barcode(
        self, current_product: Product, update_data: Dict[str, Any]
    ) -> None:
        if "barcode" not in update_data:
            return
        if update_data["barcode"] == current_product.barcode:
            return
        self._validate_barcode_unique(update_data["barcode"])

    def _finalize_product_update(
        self, product_id: int, updated_fields: List[str]
    ) -> None:
        logger.info(
            "Product updated",
            extra={"product_id": product_id, "updated_fields": updated_fields},
        )
        self.clear_cache()
        event_system.product_updated.emit(product_id)

    def _validate_product_data(
        self, data: Dict[str, Any], is_create: bool
    ) -> Dict[str, Any]:
        """
        Validate product data.

        Args:
            data: The data to validate.
            is_create: Whether this is a create operation.

        Returns:
            Dict[str, Any]: Validated data.

        Raises:
            ValidationException: If validation fails.
        """
        validated: Dict[str, Any] = {}
        validate_name_field(data, validated, is_create)
        validate_description_field(data, validated)
        validate_category_field(data, validated)
        validate_money_field(data, validated, "cost_price", "Cost Price")
        validate_money_field(data, validated, "sell_price", "Sell Price")
        validate_barcode_field(data, validated, self._validate_barcode_format)
        return validated

    @staticmethod
    def _validate_barcode_format(barcode: str) -> None:
        """
        Validate barcode format.

        Args:
            barcode: The barcode to validate.

        Raises:
            ValidationException: If barcode format is invalid.
        """
        if not barcode:
            return

        if not isinstance(barcode, str):
            raise ValidationException("Barcode must be a string")

        # Remove any whitespace
        barcode = barcode.strip()

        if len(barcode) == 0:
            return

        # Check if barcode contains only digits
        if not barcode.isdigit():
            raise ValidationException("Barcode must contain only digits")

        # Validate length - accept common barcode lengths
        valid_lengths = {8, 12, 13, 14}  # EAN-8, UPC-A, EAN-13, EAN-14
        if len(barcode) not in valid_lengths:
            raise ValidationException(
                f"Invalid barcode length. Must be one of: {valid_lengths}"
            )

    def _validate_barcode_unique(self, barcode: str) -> None:
        """
        Validate barcode uniqueness.

        Args:
            barcode: The barcode to validate.

        Raises:
            ValidationException: If barcode is not unique.
        """
        if not barcode:
            return

        existing_product = self.get_product_by_barcode(barcode)
        if existing_product:
            raise ValidationException(
                f"Barcode {barcode} is already in use by product: {existing_product.name}"
            )
