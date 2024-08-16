from typing import List, Optional
from database import DatabaseManager
from models.product import Product
from utils.validation.validators import validate, is_non_empty_string, is_positive, has_length
from utils.sanitizers import sanitize_html, sanitize_sql
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import NotFoundException, ValidationException, DatabaseException
from utils.system.logger import logger
from functools import lru_cache

class ProductService:
    @db_operation(show_dialog=True)
    #@validate_input([is_non_empty_string, has_length(1, 100)], "Invalid product name")
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        category_id: Optional[int] = None,
        cost_price: Optional[float] = None,
        sell_price: Optional[float] = None,
    ) -> Optional[int]:
        name = sanitize_html(name)
        if description:
            description = sanitize_html(description)
        
        if cost_price is not None:
            validate(cost_price, [is_positive], "Cost price must be positive")
        if sell_price is not None:
            validate(sell_price, [is_positive], "Sell price must be positive")

        query = "INSERT INTO products (name, description, category_id, cost_price, sell_price) VALUES (?, ?, ?, ?, ?)"
        params = (name, description, category_id, cost_price, sell_price)
        
        try:
            cursor = DatabaseManager.execute_query(query, params)
            product_id = cursor.lastrowid
            logger.info("Product created", product_id=product_id, name=name)
            self.clear_cache()
            return product_id
        except Exception as e:
            logger.error("Failed to create product", error=str(e), name=name)
            raise DatabaseException(f"Failed to create product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_product(self, product_id: int) -> Optional[Product]:
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
        """
        row = DatabaseManager.fetch_one(query, (product_id,))
        if row:
            logger.info("Product retrieved", product_id=product_id)
            return Product.from_db_row(row)
        else:
            logger.warning("Product not found", product_id=product_id)
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
        logger.info("All products retrieved", count=len(products))
        return products

    @db_operation(show_dialog=True)
    #@validate_input([is_non_empty_string, has_length(1, 100)], "Invalid product name")
    @handle_exceptions(NotFoundException, ValidationException, DatabaseException, show_dialog=True)
    def update_product(
        self,
        product_id: int,
        name: str,
        description: Optional[str],
        category_id: Optional[int],
        cost_price: Optional[float],
        sell_price: Optional[float],
    ) -> None:
        name = sanitize_html(name)
        if description is not None:
            description = sanitize_html(description)
        
        if cost_price is not None:
            validate(cost_price, [is_positive], "Cost price must be positive")
        if sell_price is not None:
            validate(sell_price, [is_positive], "Sell price must be positive")

        current_product = self.get_product(product_id)
        if not current_product:
            raise NotFoundException(f"No product found with ID: {product_id}")

        query = "UPDATE products SET name = ?, description = ?, category_id = ?, cost_price = ?, sell_price = ? WHERE id = ?"
        params = (name, description, category_id, cost_price, sell_price, product_id)
        
        try:
            DatabaseManager.execute_query(query, params)
            logger.info("Product updated", product_id=product_id, name=name)
            self.clear_cache()
        except Exception as e:
            logger.error("Failed to update product", error=str(e), product_id=product_id)
            raise DatabaseException(f"Failed to update product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_product(self, product_id: int) -> None:
        query = "DELETE FROM products WHERE id = ?"
        try:
            DatabaseManager.execute_query(query, (product_id,))
            logger.info("Product deleted", product_id=product_id)
            self.clear_cache()
        except Exception as e:
            logger.error("Failed to delete product", error=str(e), product_id=product_id)
            raise DatabaseException(f"Failed to delete product: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_products(self, search_term: str) -> List[Product]:
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE LOWER(CAST(p.name AS TEXT)) LIKE LOWER(?) OR LOWER(COALESCE(CAST(p.description AS TEXT), '')) LIKE LOWER(?)
        ORDER BY p.name
        """
        search_pattern = f"%{sanitize_sql(search_term)}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern, search_pattern))
        products = [Product.from_db_row(row) for row in rows]
        logger.info("Products searched", search_term=search_term, count=len(products))
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
