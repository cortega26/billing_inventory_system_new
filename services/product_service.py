from typing import List, Optional, Dict, Any
from database import DatabaseManager
from models.product import Product
from utils.validators import validate_string
from utils.logger import logger
from functools import lru_cache

class ProductService:
    @staticmethod
    def create_product(name: str, description: Optional[str] = None, category_id: Optional[int] = None, cost_price: Optional[int] = None, sell_price: Optional[int] = None) -> Optional[int]:
        try:
            logger.debug(f"Creating product with name: {name}, description: {description}, category_id: {category_id}, cost_price: {cost_price}, sell_price: {sell_price}")
            name = validate_string(name, "Product name", max_length=100)
            if description:
                description = validate_string(description, "Product description", max_length=500)
            if cost_price is not None:
                Product.validate_price(cost_price)
            if sell_price is not None:
                Product.validate_price(sell_price)
            
            query = 'INSERT INTO products (name, description, category_id, cost_price, sell_price) VALUES (?, ?, ?, ?, ?)'
            cursor = DatabaseManager.execute_query(query, (name, description, category_id, cost_price, sell_price))
            product_id = cursor.lastrowid
            logger.info(f"Created product with ID: {product_id}")
            ProductService.clear_cache()
            return product_id
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            raise

    @staticmethod
    def get_product(product_id: int) -> Optional[Product]:
        try:
            logger.debug(f"Getting product with ID: {product_id}")
            query = '''
            SELECT p.*, c.name as category_name 
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.id = ?
            '''
            row = DatabaseManager.fetch_one(query, (product_id,))
            if row:
                product = Product.from_db_row(row)
                logger.debug(f"Retrieved product: {product}")
                return product
            logger.debug(f"No product found with ID: {product_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting product: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=1)
    def get_all_products() -> List[Product]:
        try:
            logger.debug("Getting all products")
            query = '''
            SELECT p.*, c.name as category_name 
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.name
            '''
            rows = DatabaseManager.fetch_all(query)
            products = [Product.from_db_row(row) for row in rows]
            logger.debug(f"Retrieved {len(products)} products")
            return products
        except Exception as e:
            logger.error(f"Error getting all products: {str(e)}")
            raise

    @staticmethod
    def update_product(product_id: int, name: str, description: Optional[str], category_id: Optional[int], cost_price: Optional[int], sell_price: Optional[int]) -> None:
        try:
            logger.debug(f"Updating product with ID: {product_id}, name: {name}, description: {description}, category_id: {category_id}, cost_price: {cost_price}, sell_price: {sell_price}")
            name = validate_string(name, "Product name", max_length=100)
            if description is not None:
                description = validate_string(description, "Product description", max_length=500)
            if cost_price is not None:
                Product.validate_price(cost_price)
            if sell_price is not None:
                Product.validate_price(sell_price)
            
            current_product = ProductService.get_product(product_id)
            if not current_product:
                raise ValueError(f"No product found with ID: {product_id}")

            query = 'UPDATE products SET name = ?, description = ?, category_id = ?, cost_price = ?, sell_price = ? WHERE id = ?'
            DatabaseManager.execute_query(query, (name, description, category_id, cost_price, sell_price, product_id))
            
            logger.info(f"Updated product ID {product_id}")
            ProductService.clear_cache()
        except Exception as e:
            logger.error(f"Error updating product: {str(e)}")
            raise

    @staticmethod
    def delete_product(product_id: int) -> None:
        try:
            logger.debug(f"Deleting product with ID: {product_id}")
            query = 'DELETE FROM products WHERE id = ?'
            DatabaseManager.execute_query(query, (product_id,))
            logger.info(f"Deleted product with ID: {product_id}")
            ProductService.clear_cache()
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            raise

    @staticmethod
    def get_average_purchase_price(product_id: int) -> float:
        try:
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
        except Exception as e:
            logger.error(f"Error getting average purchase price: {str(e)}")
            raise

    @staticmethod
    def search_products(search_term: str) -> List[Product]:
        try:
            search_term = str(search_term)  # Ensure search_term is a string
            logger.debug(f"Searching products with term: {search_term}")
            query = '''
            SELECT p.*, c.name as category_name 
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(CAST(p.name AS TEXT)) LIKE LOWER(?) OR LOWER(COALESCE(CAST(p.description AS TEXT), '')) LIKE LOWER(?)
            ORDER BY p.name
            '''
            search_pattern = f"%{search_term}%"
            rows = DatabaseManager.fetch_all(query, (search_pattern, search_pattern))
            products = [Product.from_db_row(row) for row in rows]
            logger.debug(f"Found {len(products)} products matching search term: {search_term}")
            return products
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            logger.exception("Stack trace:")
            raise

    @staticmethod
    def get_product_sales_stats(product_id: int) -> Dict[str, Any]:
        try:
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
        except Exception as e:
            logger.error(f"Error getting product sales stats: {str(e)}")
            raise

    @staticmethod
    def get_products_by_category(category_id: int) -> List[Product]:
        try:
            logger.debug(f"Getting products for category ID: {category_id}")
            query = '''
            SELECT p.*, c.name as category_name 
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.category_id = ?
            ORDER BY p.name
            '''
            rows = DatabaseManager.fetch_all(query, (category_id,))
            products = [Product.from_db_row(row) for row in rows]
            logger.debug(f"Retrieved {len(products)} products for category ID: {category_id}")
            return products
        except Exception as e:
            logger.error(f"Error getting products by category: {str(e)}")
            raise

    @staticmethod
    def get_product_profit_margin(product_id: int) -> float:
        try:
            product = ProductService.get_product(product_id)
            if product is None:
                logger.error(f"Product with ID {product_id} not found")
                return 0
            if product.cost_price is not None and product.sell_price is not None and product.sell_price != 0:
                return (product.sell_price - product.cost_price) / product.sell_price * 100
            return 0
        except Exception as e:
            logger.error(f"Error calculating product profit margin: {str(e)}")
            return 0

    @staticmethod
    def clear_cache():
        ProductService.get_all_products.cache_clear()