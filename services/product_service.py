from typing import List, Optional, Dict, Any
from database import DatabaseManager
from models.product import Product
from utils.validation.validators import (
    validate_string, validate_integer, validate_float_non_negative
)
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import NotFoundException, ValidationException, DatabaseException
from utils.system.logger import logger
from utils.system.event_system import event_system
from functools import lru_cache
import re

class ProductService:
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_product(self, product_data: Dict[str, Any]) -> Optional[int]:
        """
        Create a new product and initialize its inventory.

        Args:
            product_data: Dictionary containing product information.
                Required: name
                Optional: description, category_id, cost_price, sell_price, barcode

        Returns:
            Optional[int]: The ID of the created product.

        Raises:
            ValidationException: If validation fails.
            DatabaseException: If database operation fails.
        """
        validated_data = self._validate_product_data(product_data, is_create=True)
        
        # Ensure barcode is in validated_data, even if None
        if 'barcode' not in validated_data:
            validated_data['barcode'] = None

        try:
            # Begin transaction
            DatabaseManager.begin_transaction()

            # Insert product
            query = """
            INSERT INTO products (
                name, description, category_id, cost_price, sell_price, barcode
            ) VALUES (
                :name, :description, :category_id, :cost_price, :sell_price, :barcode
            )
            """
            cursor = DatabaseManager.execute_query(query, validated_data)
            product_id = cursor.lastrowid

            if product_id:
                # Initialize inventory with 0 quantity
                inventory_query = """
                INSERT INTO inventory (product_id, quantity) 
                VALUES (?, 0.000)
                """
                DatabaseManager.execute_query(inventory_query, (product_id,))

                # Commit transaction
                DatabaseManager.commit_transaction()

                logger.info("Product created with inventory initialized", extra={
                    "product_id": product_id,
                    "name": validated_data['name']
                })
                
                # Clear any caches
                self.clear_cache()
                
                return product_id
            else:
                raise DatabaseException("Failed to create product: No product ID returned")

        except Exception as e:
            # Rollback transaction on error
            DatabaseManager.rollback_transaction()
            logger.error("Failed to create product", extra={
                "error": str(e),
                "data": validated_data
            })
            raise DatabaseException(f"Failed to create product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_product(self, product_id: int) -> Optional[Product]:
        """
        Get a product by ID.

        Args:
            product_id: The product ID.

        Returns:
            Optional[Product]: The product if found.

        Raises:
            NotFoundException: If product not found.
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
        else:
            logger.warning("Product not found", extra={"product_id": product_id})
            raise NotFoundException(f"Product with ID {product_id} not found")

    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_products(self) -> List[Product]:
        """Get all products with fresh data."""
        query = """
        SELECT DISTINCT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.id
        """
        try:
            rows = DatabaseManager.fetch_all(query)
            products = [Product.from_db_row(row) for row in rows]
            logger.info(f"Retrieved {len(products)} products")
            return products
        except Exception as e:
            logger.error(f"Error retrieving products: {str(e)}")
            raise DatabaseException(f"Failed to retrieve products: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, ValidationException, DatabaseException, show_dialog=True)
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
        
        # Fetch current product to ensure it exists
        current_product = self.get_product(product_id)
        if not current_product:
            raise NotFoundException(f"No product found with ID: {product_id}")

        # Validate barcode if provided
        if 'barcode' in update_data and update_data['barcode'] != current_product.barcode:
            self._validate_barcode_unique(update_data['barcode'])

        # Validate and prepare update data
        validated_data = self._validate_product_data(update_data, is_create=False)
        
        if not validated_data:
            logger.warning("No valid fields to update", extra={"product_id": product_id})
            return

        # Prepare SQL query
        set_clause = ", ".join(f"{key} = :{key}" for key in validated_data.keys())
        query = f"UPDATE products SET {set_clause} WHERE id = :product_id"
        validated_data['product_id'] = product_id

        try:
            DatabaseManager.execute_query(query, validated_data)
            logger.info("Product updated", extra={
                "product_id": product_id,
                "updated_fields": list(validated_data.keys())
            })
            self.clear_cache()
            event_system.product_updated.emit(product_id)
        except Exception as e:
            logger.error("Failed to update product", extra={
                "error": str(e),
                "product_id": product_id
            })
            raise DatabaseException(f"Failed to update product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    @db_operation(show_dialog=True)
    def delete_product(self, product_id: int) -> None:
        """Delete a product and clear caches."""
        product_id = validate_integer(product_id, min_value=1)
        
        try:
            # Begin transaction
            DatabaseManager.begin_transaction()
            
            # First delete related records
            DatabaseManager.execute_query(
                "DELETE FROM sale_items WHERE product_id = ?", 
                (product_id,)
            )
            
            DatabaseManager.execute_query(
                "DELETE FROM purchase_items WHERE product_id = ?", 
                (product_id,)
            )
            
            DatabaseManager.execute_query(
                "DELETE FROM inventory WHERE product_id = ?", 
                (product_id,)
            )
            
            # Finally delete the product
            query = "DELETE FROM products WHERE id = ?"
            cursor = DatabaseManager.execute_query(query, (product_id,))
            
            if cursor.rowcount == 0:
                DatabaseManager.rollback_transaction()
                raise NotFoundException(f"Product with ID {product_id} not found")
                
            # Commit all changes
            DatabaseManager.commit_transaction()
            
            # Clear the cache
            self.clear_cache()
            
            logger.info(f"Product deleted successfully: ID {product_id}")
            
        except Exception as e:
            DatabaseManager.rollback_transaction()
            logger.error(f"Failed to delete product", extra={"error": str(e), "product_id": product_id})
            raise DatabaseException(f"Failed to delete product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_products(self, search_term: str) -> List[Product]:
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
        WHERE LOWER(p.name) LIKE LOWER(:search_pattern) 
           OR LOWER(COALESCE(p.description, '')) LIKE LOWER(:search_pattern)
           OR LOWER(COALESCE(p.barcode, '')) LIKE LOWER(:search_pattern)
        ORDER BY p.name
        """
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(query, {"search_pattern": search_pattern})
        products = [Product.from_db_row(row) for row in rows]
        logger.info("Products searched", extra={
            "search_term": search_term,
            "count": len(products)
        })
        return products

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_product_by_barcode(self, barcode: str) -> Optional[Product]:
        """
        Get a product by its barcode.

        Args:
            barcode: The product barcode.

        Returns:
            Optional[Product]: The product if found.

        Raises:
            DatabaseException: If database operation fails.
        """
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.barcode = :barcode
        """
        row = DatabaseManager.fetch_one(query, {"barcode": barcode})
        if row:
            logger.info("Product retrieved by barcode", extra={"barcode": barcode})
            return Product.from_db_row(row)
        logger.info("No product found with barcode", extra={"barcode": barcode})
        return None

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
            product = self.get_product(product_id)
            if product is None:
                logger.warning(f"Product not found for ID: {product_id}")
                raise NotFoundException(f"Product with ID {product_id} not found")
            
            if product.cost_price is None or product.sell_price is None:
                logger.info(f"Unable to calculate profit margin for product {product_id}: cost_price or sell_price is None")
                return 0
            
            if product.sell_price == 0:
                logger.warning(f"Sell price is zero for product {product_id}, unable to calculate profit margin")
                return 0
            
            profit_margin = int((product.sell_price - product.cost_price) / product.sell_price * 100)
            logger.info(f"Calculated profit margin for product {product_id}: {profit_margin}%")
            return profit_margin
        except Exception as e:
            logger.error(f"Error calculating profit margin for product {product_id}: {str(e)}")
            raise

    def clear_cache(self):
        """Clear the product cache."""
        self.get_all_products.cache_clear()
        logger.debug("Product cache cleared")

    def _validate_product_data(self, data: Dict[str, Any], is_create: bool) -> Dict[str, Any]:
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
        validated = {}
        if 'name' in data or is_create:
            validated['name'] = validate_string(
                data.get('name', ''), min_length=1, max_length=100
            )
        
        if 'description' in data:
            validated['description'] = validate_string(
                data.get('description', ''), min_length=0, max_length=500
            )
        
        if 'category_id' in data:
            category_id = data.get('category_id')
            validated['category_id'] = validate_integer(
                category_id, min_value=1
            ) if category_id is not None else None
        
        if 'cost_price' in data:
            cost_price = data.get('cost_price')
            if cost_price is not None:
                validated['cost_price'] = validate_integer(cost_price, min_value=0)
        
        if 'sell_price' in data:
            sell_price = data.get('sell_price')
            if sell_price is not None:
                validated['sell_price'] = validate_integer(sell_price, min_value=0)

        if 'barcode' in data:
            barcode = data.get('barcode')
            if barcode is not None:
                self._validate_barcode_format(barcode)
                validated['barcode'] = barcode
        
        if is_create and 'name' not in validated:
            raise ValidationException("Product name is required when creating a product")
        
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
