from typing import List, Optional, Dict, Any
from database import DatabaseManager
from models.product import Product
from utils.validation.validators import validate_string, validate_float, validate_integer
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import NotFoundException, ValidationException, DatabaseException
from utils.system.logger import logger
from utils.system.event_system import event_system
from functools import lru_cache

class ProductService:
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_product(self, product_data: Dict[str, Any]) -> Optional[int]:
        validated_data = self._validate_product_data(product_data, is_create=True)
        query = """
        INSERT INTO products (name, description, category_id, cost_price, sell_price) 
        VALUES (:name, :description, :category_id, :cost_price, :sell_price)
        """
        try:
            cursor = DatabaseManager.execute_query(query, validated_data)
            product_id = cursor.lastrowid
            logger.info("Product created", extra={"product_id": product_id, "name": validated_data['name']})
            self.clear_cache()
            event_system.product_added.emit(product_id)
            return product_id
        except Exception as e:
            logger.error("Failed to create product", extra={"error": str(e), "data": validated_data})
            raise DatabaseException(f"Failed to create product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_product(self, product_id: int) -> Optional[Product]:
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
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.name
        """
        rows = DatabaseManager.fetch_all(query)
        products = [Product.from_db_row(row) for row in rows]
        logger.info("All products retrieved", extra={"count": len(products)})
        return products

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, ValidationException, DatabaseException, show_dialog=True)
    def update_product(self, product_id: int, update_data: Dict[str, Any]) -> None:
        product_id = validate_integer(product_id, min_value=1)
        
        # Fetch current product to ensure it exists
        current_product = self.get_product(product_id)
        if not current_product:
            raise NotFoundException(f"No product found with ID: {product_id}")

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
            logger.info("Product updated", extra={"product_id": product_id, "updated_fields": list(validated_data.keys())})
            self.clear_cache()
            event_system.product_updated.emit(product_id)
        except Exception as e:
            logger.error("Failed to update product", extra={"error": str(e), "product_id": product_id})
            raise DatabaseException(f"Failed to update product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_product(self, product_id: int) -> None:
        product_id = validate_integer(product_id, min_value=1)
        query = "DELETE FROM products WHERE id = :product_id"
        try:
            DatabaseManager.execute_query(query, {"product_id": product_id})
            logger.info("Product deleted", extra={"product_id": product_id})
            self.clear_cache()
            event_system.product_deleted.emit(product_id)
        except Exception as e:
            logger.error("Failed to delete product", extra={"error": str(e), "product_id": product_id})
            raise DatabaseException(f"Failed to delete product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_products(self, search_term: str) -> List[Product]:
        search_term = validate_string(search_term, max_length=100)
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE LOWER(p.name) LIKE LOWER(:search_pattern) OR LOWER(COALESCE(p.description, '')) LIKE LOWER(:search_pattern)
        ORDER BY p.name
        """
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(query, {"search_pattern": search_pattern})
        products = [Product.from_db_row(row) for row in rows]
        logger.info("Products searched", extra={"search_term": search_term, "count": len(products)})
        return products

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_product_profit_margin(self, product_id: int) -> float:
        try:
            product = self.get_product(product_id)
            if product is None:
                logger.warning(f"Product not found for ID: {product_id}")
                raise NotFoundException(f"Product with ID {product_id} not found")
            
            if product.cost_price is None or product.sell_price is None:
                logger.info(f"Unable to calculate profit margin for product {product_id}: cost_price or sell_price is None")
                return 0.0
            
            if product.sell_price == 0:
                logger.warning(f"Sell price is zero for product {product_id}, unable to calculate profit margin")
                return 0.0
            
            profit_margin = (product.sell_price - product.cost_price) / product.sell_price * 100
            rounded_margin = round(profit_margin, 2)
            logger.info(f"Calculated profit margin for product {product_id}: {rounded_margin}%")
            return rounded_margin
        except Exception as e:
            logger.error(f"Error calculating profit margin for product {product_id}: {str(e)}")
            raise

    def clear_cache(self):
        self.get_all_products.cache_clear()
        logger.debug("Product cache cleared")

    def _validate_product_data(self, data: Dict[str, Any], is_create: bool) -> Dict[str, Any]:
        validated = {}
        if 'name' in data or is_create:
            validated['name'] = validate_string(data.get('name', ''), min_length=1, max_length=100)
        if 'description' in data:
            validated['description'] = validate_string(data.get('description', ''), min_length=1, max_length=500)
        if 'category_id' in data:
            category_id = data.get('category_id')
            validated['category_id'] = validate_integer(category_id, min_value=1) if category_id is not None else None
        if 'cost_price' in data:
            cost_price = data.get('cost_price')
            validated['cost_price'] = validate_float(cost_price, min_value=0) if cost_price is not None else None
        if 'sell_price' in data:
            sell_price = data.get('sell_price')
            validated['sell_price'] = validate_float(sell_price, min_value=0) if sell_price is not None else None
        
        if is_create and 'name' not in validated:
            raise ValidationException("Product name is required when creating a product")
        
        return validated