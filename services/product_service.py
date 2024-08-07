from typing import List, Optional, Dict, Any
from database import DatabaseManager
from models.product import Product
from utils.validation.validators import validate_string
from utils.decorators import db_operation, validate_input
from utils.exceptions import NotFoundException
from functools import lru_cache


class ProductService:
    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def create_product(
        name: str,
        description: Optional[str] = None,
        category_id: Optional[int] = None,
        cost_price: Optional[int] = None,
        sell_price: Optional[int] = None,
    ) -> Optional[int]:
        name = validate_string(name, "Product name", max_length=100)
        if description:
            description = validate_string(
                description, "Product description", max_length=500
            )
        ProductService._validate_prices(cost_price, sell_price)

        query = "INSERT INTO products (name, description, category_id, cost_price, sell_price) VALUES (?, ?, ?, ?, ?)"
        cursor = DatabaseManager.execute_query(
            query, (name, description, category_id, cost_price, sell_price)
        )
        product_id = cursor.lastrowid
        ProductService.clear_cache()
        return product_id

    @staticmethod
    @db_operation(show_dialog=True)
    def get_product(product_id: int) -> Optional[Product]:
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
        """
        row = DatabaseManager.fetch_one(query, (product_id,))
        return Product.from_db_row(row) if row else None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    def get_all_products() -> List[Product]:
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.name
        """
        rows = DatabaseManager.fetch_all(query)
        return [Product.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def update_product(
        product_id: int,
        name: str,
        description: Optional[str],
        category_id: Optional[int],
        cost_price: Optional[int],
        sell_price: Optional[int],
    ) -> None:
        name = validate_string(name, "Product name", max_length=100)
        if description is not None:
            description = validate_string(
                description, "Product description", max_length=500
            )
        ProductService._validate_prices(cost_price, sell_price)

        current_product = ProductService.get_product(product_id)
        if not current_product:
            raise NotFoundException(f"No product found with ID: {product_id}")

        query = "UPDATE products SET name = ?, description = ?, category_id = ?, cost_price = ?, sell_price = ? WHERE id = ?"
        DatabaseManager.execute_query(
            query, (name, description, category_id, cost_price, sell_price, product_id)
        )
        ProductService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def delete_product(product_id: int) -> None:
        query = "DELETE FROM products WHERE id = ?"
        DatabaseManager.execute_query(query, (product_id,))
        ProductService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def get_average_purchase_price(product_id: int) -> float:
        query = """
            SELECT AVG(price) as avg_price
            FROM purchase_items
            WHERE product_id = ?
        """
        result = DatabaseManager.fetch_one(query, (product_id,))
        return float(
            result["avg_price"] if result and result["avg_price"] is not None else 0
        )

    @staticmethod
    @db_operation(show_dialog=True)
    def search_products(search_term: str) -> List[Product]:
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE LOWER(CAST(p.name AS TEXT)) LIKE LOWER(?) OR LOWER(COALESCE(CAST(p.description AS TEXT), '')) LIKE LOWER(?)
        ORDER BY p.name
        """
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern, search_pattern))
        return [Product.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    def get_product_sales_stats(product_id: int) -> Dict[str, Any]:
        query = """
        SELECT 
            COUNT(si.id) as total_sales,
            SUM(si.quantity) as total_quantity_sold,
            SUM(si.quantity * si.price) as total_revenue
        FROM sale_items si
        WHERE si.product_id = ?
        """
        result = DatabaseManager.fetch_one(query, (product_id,))
        return {
            "total_sales": result["total_sales"] if result else 0,
            "total_quantity_sold": result["total_quantity_sold"] if result else 0,
            "total_revenue": (
                float(result["total_revenue"])
                if result and result["total_revenue"]
                else 0.0
            ),
        }

    @staticmethod
    @db_operation(show_dialog=True)
    def get_products_by_category(category_id: int) -> List[Product]:
        query = """
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.category_id = ?
        ORDER BY p.name
        """
        rows = DatabaseManager.fetch_all(query, (category_id,))
        return [Product.from_db_row(row) for row in rows]

    @staticmethod
    def get_product_profit_margin(product_id: int) -> float:
        product = ProductService.get_product(product_id)
        if product is None:
            return 0
        if (
            product.cost_price is not None
            and product.sell_price is not None
            and product.sell_price != 0
        ):
            return (product.sell_price - product.cost_price) / product.sell_price * 100
        return 0

    @staticmethod
    def clear_cache():
        ProductService.get_all_products.cache_clear()

    @staticmethod
    def _validate_prices(cost_price: Optional[int], sell_price: Optional[int]) -> None:
        if cost_price is not None:
            Product.validate_price(cost_price)
        if sell_price is not None:
            Product.validate_price(sell_price)
