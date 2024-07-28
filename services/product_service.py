from typing import List, Optional
from database import DatabaseManager
from models.product import Product
from utils.validators import validate_string

from utils.logger import logger

class ProductService:
    @staticmethod
    def create_product(name: str, description: Optional[str] = None) -> Optional[int]:
        logger.debug(f"Creating product with name: {name}, description: {description}")
        name = validate_string(name, "Product name", max_length=100)
        if description:
            description = validate_string(description, "Product description", max_length=500)
        
        query = 'INSERT INTO products (name, description) VALUES (?, ?)'
        cursor = DatabaseManager.execute_query(query, (name, description))
        product_id = cursor.lastrowid
        logger.debug(f"Created product with ID: {product_id}")
        return product_id if product_id is not None else None

    @staticmethod
    def get_product(product_id: int) -> Optional[Product]:
        logger.debug(f"Getting product with ID: {product_id}")
        query = 'SELECT * FROM products WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (product_id,))
        if row:
            product = Product.from_row(row)
            logger.debug(f"Retrieved product: {product}")
            return product
        logger.debug(f"No product found with ID: {product_id}")
        return None

    @staticmethod
    def get_all_products() -> List[Product]:
        logger.debug("Getting all products")
        query = 'SELECT * FROM products'
        rows = DatabaseManager.fetch_all(query)
        products = [Product.from_row(row) for row in rows]
        logger.debug(f"Retrieved {len(products)} products")
        return products

    @staticmethod
    def update_product(product_id: int, name: str, description: str) -> None:
        logger.debug(f"Updating product with ID: {product_id}, name: {name}, description: {description}")
        query = 'UPDATE products SET name = ?, description = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (name, description, product_id))
        logger.debug(f"Product updated successfully")

    @staticmethod
    def delete_product(product_id: int) -> None:
        query = 'DELETE FROM products WHERE id = ?'
        DatabaseManager.execute_query(query, (product_id,))

    @staticmethod
    def get_average_purchase_price(product_id: int) -> int:
        query = '''
            SELECT CAST(AVG(price) AS INTEGER) as avg_price
            FROM purchase_items
            WHERE product_id = ?
        '''
        result = DatabaseManager.fetch_one(query, (product_id,))
        return result['avg_price'] if result and result['avg_price'] is not None else 0