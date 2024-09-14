from typing import List, Optional, Dict, Any
from database import DatabaseManager
from models.category import Category
from utils.validation.validators import validate_string, validate_integer
from utils.sanitizers import sanitize_html, sanitize_sql
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import ValidationException, NotFoundException, DatabaseException
from utils.system.logger import logger
from utils.system.event_system import event_system
from functools import lru_cache

class CategoryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_category(name: str) -> Optional[int]:
        name = validate_string(name, min_length=1, max_length=50)
        name = sanitize_html(name)
        query = "INSERT INTO categories (name) VALUES (?)"
        try:
            cursor = DatabaseManager.execute_query(query, (name,))
            category_id = cursor.lastrowid
            CategoryService.clear_cache()
            logger.info("Category created", extra={"category_id": category_id, "name": name})
            event_system.category_added.emit(category_id)
            return category_id
        except Exception as e:
            logger.error("Failed to create category", extra={"error": str(e), "name": name})
            raise DatabaseException(f"Failed to create category: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_category(category_id: int) -> Optional[Category]:
        category_id = validate_integer(category_id, min_value=1)
        query = "SELECT * FROM categories WHERE id = ?"
        row = DatabaseManager.fetch_one(query, (category_id,))
        if row:
            logger.info("Category retrieved", extra={"category_id": category_id})
            return Category.from_db_row(row)
        else:
            logger.warning("Category not found", extra={"category_id": category_id})
            raise NotFoundException(f"Category with ID {category_id} not found")

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_categories() -> List[Category]:
        query = "SELECT * FROM categories ORDER BY name"
        rows = DatabaseManager.fetch_all(query)
        categories = [Category.from_db_row(row) for row in rows]
        logger.info("All categories retrieved", extra={"count": len(categories)})
        return categories

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, ValidationException, DatabaseException, show_dialog=True)
    def update_category(category_id: int, name: str) -> None:
        category_id = validate_integer(category_id, min_value=1)
        name = validate_string(name, min_length=1, max_length=50)
        name = sanitize_html(name)
        query = "UPDATE categories SET name = ? WHERE id = ?"
        try:
            cursor = DatabaseManager.execute_query(query, (name, category_id))
            if cursor.rowcount == 0:
                raise NotFoundException(f"Category with ID {category_id} not found")
            CategoryService.clear_cache()
            logger.info("Category updated", extra={"category_id": category_id, "new_name": name})
            event_system.category_updated.emit(category_id)
        except Exception as e:
            logger.error("Failed to update category", extra={"error": str(e), "category_id": category_id})
            raise DatabaseException(f"Failed to update category: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_category(category_id: int) -> None:
        category_id = validate_integer(category_id, min_value=1)
        query = "DELETE FROM categories WHERE id = ?"
        try:
            cursor = DatabaseManager.execute_query(query, (category_id,))
            if cursor.rowcount == 0:
                raise NotFoundException(f"Category with ID {category_id} not found")
            CategoryService.clear_cache()
            logger.info("Category deleted", extra={"category_id": category_id})
            event_system.category_deleted.emit(category_id)
        except Exception as e:
            logger.error("Failed to delete category", extra={"error": str(e), "category_id": category_id})
            raise DatabaseException(f"Failed to delete category: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_categories(search_term: str) -> List[Category]:
        search_term = validate_string(search_term, max_length=50)
        query = """
        SELECT * FROM categories
        WHERE name LIKE ?
        ORDER BY name
        """
        search_pattern = f"%{sanitize_sql(search_term)}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern,))
        categories = [Category.from_db_row(row) for row in rows]
        logger.info("Categories searched", extra={"search_term": search_term, "count": len(categories)})
        return categories

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_category_by_name(name: str) -> Optional[Category]:
        name = validate_string(name, min_length=1, max_length=50)
        query = "SELECT * FROM categories WHERE name = ?"
        row = DatabaseManager.fetch_one(query, (name,))
        if row:
            logger.info("Category retrieved by name", extra={"name": name})
            return Category.from_db_row(row)
        else:
            logger.warning("Category not found by name", extra={"name": name})
            raise NotFoundException(f"Category with name '{name}' not found")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_products_in_category(category_id: int) -> List[Dict[str, Any]]:
        category_id = validate_integer(category_id, min_value=1)
        query = """
        SELECT p.id, p.name, p.description, p.cost_price, p.sell_price
        FROM products p
        WHERE p.category_id = ?
        """
        rows = DatabaseManager.fetch_all(query, (category_id,))
        logger.info("Products retrieved for category", extra={"category_id": category_id, "count": len(rows)})
        return rows

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_category_statistics() -> List[Dict[str, Any]]:
        query = """
        SELECT 
            c.id, 
            c.name, 
            COUNT(p.id) as product_count,
            COALESCE(SUM(i.quantity), 0) as total_inventory,
            COALESCE(SUM(p.sell_price * i.quantity), 0) as inventory_value
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        LEFT JOIN inventory i ON p.id = i.product_id
        GROUP BY c.id
        ORDER BY c.name
        """
        rows = DatabaseManager.fetch_all(query)
        logger.info("Category statistics retrieved", extra={"count": len(rows)})
        return rows

    @staticmethod
    def clear_cache():
        CategoryService.get_all_categories.cache_clear()
        logger.debug("Category cache cleared")
