from typing import List, Optional
from database import DatabaseManager
from models.product import Product

class ProductService:
    @staticmethod
    def create_product(name: str, description: str) -> Optional[int]:
        query = 'INSERT INTO products (name, description) VALUES (?, ?)'
        cursor = DatabaseManager.execute_query(query, (name, description))
        return cursor.lastrowid if cursor.lastrowid is not None else None

    @staticmethod
    def get_product(product_id: int) -> Optional[Product]:
        query = 'SELECT * FROM products WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (product_id,))
        return Product.from_row(row) if row else None

    @staticmethod
    def get_all_products() -> List[Product]:
        query = 'SELECT * FROM products'
        rows = DatabaseManager.fetch_all(query)
        return [Product.from_row(row) for row in rows]

    @staticmethod
    def update_product(product_id: int, name: str, description: str) -> None:
        query = 'UPDATE products SET name = ?, description = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (name, description, product_id))

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