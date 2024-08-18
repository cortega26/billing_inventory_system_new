from typing import List, Optional
from database import DatabaseManager
from models.product import Product
from utils.validation.validators import is_string, validate_string, validate_float, validate_integer
from utils.decorators import db_operation, handle_exceptions, validate_input
from utils.exceptions import NotFoundException, ValidationException, DatabaseException
from utils.system.logger import logger
from utils.system.event_system import event_system
from functools import lru_cache

class ProductService:
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    @validate_input([lambda x: is_string(x, min_length=1, max_length=100)], "Invalid product name")
    def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        category_id: Optional[int] = None,
        cost_price: Optional[float] = None,
        sell_price: Optional[float] = None,
    ) -> Optional[int]:
        if description:
            description = validate_string(description, max_length=500)
        if category_id is not None:
            category_id = validate_integer(category_id, min_value=1)
        if cost_price is not None:
            cost_price = validate_float(cost_price, min_value=0)
        if sell_price is not None:
            sell_price = validate_float(sell_price, min_value=0)

        query = "INSERT INTO products (name, description, category_id, cost_price, sell_price) VALUES (?, ?, ?, ?, ?)"
        params = (name, description, category_id, cost_price, sell_price)
        
        try:
            cursor = DatabaseManager.execute_query(query, params)
            product_id = cursor.lastrowid
            logger.info("Product created", extra={"product_id": product_id, "name": name})
            self.clear_cache()
            event_system.product_added.emit(product_id)
            return product_id
        except Exception as e:
            logger.error("Failed to create product", extra={"error": str(e), "name": name})
            raise DatabaseException(f"Failed to create product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_product(self, product_id: int) -> Optional[Product]:
        product_id = validate_integer(product_id, min_value=1)
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
        """
        row = DatabaseManager.fetch_one(query, (product_id,))
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
    @validate_input([lambda x: is_string(x, min_length=1, max_length=100)], "Invalid product name")
    def update_product(
        self,
        product_id: int,
        name: str,
        description: Optional[str],
        category_id: Optional[int],
        cost_price: Optional[float],
        sell_price: Optional[float],
    ) -> None:
        product_id = validate_integer(product_id, min_value=1)
        if description is not None:
            description = validate_string(description, max_length=500)
        if category_id is not None:
            category_id = validate_integer(category_id, min_value=1)
        if cost_price is not None:
            cost_price = validate_float(cost_price, min_value=0)
        if sell_price is not None:
            sell_price = validate_float(sell_price, min_value=0)

        current_product = self.get_product(product_id)
        if not current_product:
            raise NotFoundException(f"No product found with ID: {product_id}")

        query = "UPDATE products SET name = ?, description = ?, category_id = ?, cost_price = ?, sell_price = ? WHERE id = ?"
        params = (name, description, category_id, cost_price, sell_price, product_id)
        
        try:
            DatabaseManager.execute_query(query, params)
            logger.info("Product updated", extra={"product_id": product_id, "name": name})
            self.clear_cache()
            event_system.product_updated.emit(product_id)
        except Exception as e:
            logger.error("Failed to update product", extra={"error": str(e), "product_id": product_id})
            raise DatabaseException(f"Failed to update product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_product(self, product_id: int) -> None:
        product_id = validate_integer(product_id, min_value=1)
        query = "DELETE FROM products WHERE id = ?"
        try:
            DatabaseManager.execute_query(query, (product_id,))
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
        WHERE LOWER(CAST(p.name AS TEXT)) LIKE LOWER(?) OR LOWER(COALESCE(CAST(p.description AS TEXT), '')) LIKE LOWER(?)
        ORDER BY p.name
        """
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern, search_pattern))
        products = [Product.from_db_row(row) for row in rows]
        logger.info("Products searched", extra={"search_term": search_term, "count": len(products)})
        return products

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_product_profit_margin(self, product_id: int) -> float:
        product = self.get_product(product_id)
        if product is None:
            raise NotFoundException(f"Product with ID {product_id} not found")
        
        if product.cost_price is None or product.sell_price is None or product.sell_price == 0:
            return 0.0
        
        profit_margin = (product.sell_price - product.cost_price) / product.sell_price * 100
        return round(profit_margin, 2)

    def clear_cache(self):
        self.get_all_products.cache_clear()
        logger.debug("Product cache cleared")