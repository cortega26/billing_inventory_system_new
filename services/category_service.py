from typing import List, Optional, Dict, Any
from database import DatabaseManager
from models.category import Category
from utils.validation.validators import is_non_empty_string, has_length
from utils.sanitizers import sanitize_html, sanitize_sql
from utils.decorators import db_operation, handle_exceptions, validate_input
from utils.exceptions import ValidationException, NotFoundException, DatabaseException
from utils.system.logger import logger
from functools import lru_cache

class CategoryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input([is_non_empty_string, has_length(1, 50)], "Invalid category name")
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_category(name: str) -> Optional[int]:
        name = sanitize_html(name)
        query = "INSERT INTO categories (name) VALUES (?)"
        try:
            cursor = DatabaseManager.execute_query(query, (name,))
            category_id = cursor.lastrowid
            CategoryService.clear_cache()
            logger.info(f"Category created: {name}", category_id=category_id)
            return category_id
        except Exception as e:
            logger.error(f"Failed to create category: {name}", error=str(e))
            raise DatabaseException(f"Failed to create category: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_category(category_id: int) -> Optional[Category]:
        query = "SELECT * FROM categories WHERE id = ?"
        row = DatabaseManager.fetch_one(query, (category_id,))
        if row:
            logger.info(f"Category retrieved", category_id=category_id)
            return Category.from_db_row(row)
        else:
            logger.warning(f"Category not found", category_id=category_id)
            raise NotFoundException(f"Category with ID {category_id} not found")

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_categories() -> List[Category]:
        query = "SELECT * FROM categories ORDER BY name"
        rows = DatabaseManager.fetch_all(query)
        categories = [Category.from_db_row(row) for row in rows]
        logger.info(f"All categories retrieved, count: {len(categories)}")
        return categories

    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input([is_non_empty_string, has_length(1, 50)], "Invalid category name")
    @handle_exceptions(NotFoundException, ValidationException, DatabaseException, show_dialog=True)
    def update_category(category_id: int, name: str) -> None:
        name = sanitize_html(name)
        query = "UPDATE categories SET name = ? WHERE id = ?"
        try:
            DatabaseManager.execute_query(query, (name, category_id))
            CategoryService.clear_cache()
            logger.info(f"Category updated", category_id=category_id, new_name=name)
        except Exception as e:
            logger.error(f"Failed to update category", category_id=category_id, error=str(e))
            raise DatabaseException(f"Failed to update category: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_category(category_id: int) -> None:
        query = "DELETE FROM categories WHERE id = ?"
        try:
            DatabaseManager.execute_query(query, (category_id,))
            CategoryService.clear_cache()
            logger.info(f"Category deleted", category_id=category_id)
        except Exception as e:
            logger.error(f"Failed to delete category", category_id=category_id, error=str(e))
            raise DatabaseException(f"Failed to delete category: {str(e)}")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_categories(search_term: str) -> List[Category]:
        query = """
        SELECT * FROM categories
        WHERE name LIKE ?
        ORDER BY name
        """
        search_pattern = f"%{sanitize_sql(search_term)}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern,))
        categories = [Category.from_db_row(row) for row in rows]
        logger.info(f"Categories searched", search_term=search_term, count=len(categories))
        return categories

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_category_by_name(name: str) -> Optional[Category]:
        query = "SELECT * FROM categories WHERE name = ?"
        row = DatabaseManager.fetch_one(query, (name,))
        if row:
            logger.info(f"Category retrieved by name", name=name)
            return Category.from_db_row(row)
        else:
            logger.warning(f"Category not found by name", name=name)
            raise NotFoundException(f"Category with name '{name}' not found")

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_products_in_category(category_id: int) -> List[Dict[str, Any]]:
        query = """
        SELECT p.id, p.name, p.description
        FROM products p
        WHERE p.category_id = ?
        """
        rows = DatabaseManager.fetch_all(query, (category_id,))
        logger.info(f"Products retrieved for category", category_id=category_id, count=len(rows))
        return rows

    @staticmethod
    def clear_cache():
        CategoryService.get_all_categories.cache_clear()
        logger.debug("Category cache cleared")
