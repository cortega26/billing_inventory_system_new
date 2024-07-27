from database import execute_query, fetch_one, fetch_all
from models.product import Product

class ProductService:
    @staticmethod
    def create_product(name, description):
        query = 'INSERT INTO products (name, description) VALUES (?, ?)'
        cursor = execute_query(query, (name, description))
        return cursor.lastrowid

    @staticmethod
    def get_product(product_id):
        query = 'SELECT * FROM products WHERE id = ?'
        row = fetch_one(query, (product_id,))
        return Product.from_row(row) if row else None

    @staticmethod
    def get_all_products():
        query = 'SELECT * FROM products'
        rows = fetch_all(query)
        return [Product.from_row(row) for row in rows]

    @staticmethod
    def update_product(product_id, name, description):
        query = 'UPDATE products SET name = ?, description = ? WHERE id = ?'
        execute_query(query, (name, description, product_id))

    @staticmethod
    def delete_product(product_id):
        query = 'DELETE FROM products WHERE id = ?'
        execute_query(query, (product_id,))

    @staticmethod
    def get_average_purchase_price(product_id):
        query = '''
            SELECT AVG(price) as avg_price
            FROM purchase_items
            WHERE product_id = ?
        '''
        result = fetch_one(query, (product_id,))
        return result['avg_price'] if result and result['avg_price'] is not None else 0