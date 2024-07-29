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
            product = Product.from_db_row(row)
            logger.debug(f"Retrieved product: {product}")
            return product
        logger.debug(f"No product found with ID: {product_id}")
        return None

    @staticmethod
    def get_all_products() -> List[Product]:
        logger.debug("Getting all products")
        query = 'SELECT * FROM products'
        rows = DatabaseManager.fetch_all(query)
        products = [Product.from_db_row(row) for row in rows]
        logger.debug(f"Retrieved {len(products)} products")
        return products

    @staticmethod
    def update_product(product_id: int, name: str, description: Optional[str]) -> None:
        logger.debug(f"Updating product with ID: {product_id}, name: {name}, description: {description}")
        name = validate_string(name, "Product name", max_length=100)
        if description is not None:
            description = validate_string(description, "Product description", max_length=500)
        query = 'UPDATE products SET name = ?, description = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (name, description, product_id))
        logger.debug(f"Product updated successfully")

    @staticmethod
    def delete_product(product_id: int) -> None:
        logger.debug(f"Deleting product with ID: {product_id}")
        query = 'DELETE FROM products WHERE id = ?'
        DatabaseManager.execute_query(query, (product_id,))
        logger.info(f"Deleted product with ID: {product_id}")

    @staticmethod
    def get_average_purchase_price(product_id: int) -> float:
        logger.debug(f"Getting average purchase price for product ID: {product_id}")
        query = '''
            SELECT AVG(price) as avg_price
            FROM purchase_items
            WHERE product_id = ?
        '''
        result = DatabaseManager.fetch_one(query, (product_id,))
        avg_price = result['avg_price'] if result and result['avg_price'] is not None else 0
        logger.debug(f"Average purchase price for product ID {product_id}: {avg_price}")
        return float(avg_price)

    @staticmethod
    def search_products(search_term: str) -> List[Product]:
        logger.debug(f"Searching products with term: {search_term}")
        query = '''
        SELECT * FROM products
        WHERE name LIKE ? OR description LIKE ?
        '''
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern, search_pattern))
        products = [Product.from_db_row(row) for row in rows]
        logger.debug(f"Found {len(products)} products matching search term: {search_term}")
        return products

    @staticmethod
    def get_product_sales_stats(product_id: int) -> dict:
        logger.debug(f"Getting sales stats for product ID: {product_id}")
        query = '''
        SELECT 
            COUNT(si.id) as total_sales,
            SUM(si.quantity) as total_quantity_sold,
            SUM(si.quantity * si.price) as total_revenue
        FROM sale_items si
        WHERE si.product_id = ?
        '''
        result = DatabaseManager.fetch_one(query, (product_id,))
        stats = {
            'total_sales': result['total_sales'] if result else 0,
            'total_quantity_sold': result['total_quantity_sold'] if result else 0,
            'total_revenue': float(result['total_revenue']) if result and result['total_revenue'] else 0.0
        }
        logger.debug(f"Sales stats for product ID {product_id}: {stats}")
        return stats