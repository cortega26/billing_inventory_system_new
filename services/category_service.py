from functools import lru_cache

from database.database_manager import DatabaseManager
from models.category import Category
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, NotFoundException, ValidationException
from utils.sanitizers import sanitize_html, sanitize_sql
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.validation.validators import validate_integer, validate_string


class CategoryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_category(name: str) -> int:
        name = validate_string(name, min_length=1, max_length=50)
        name = sanitize_html(name)
        query = "INSERT INTO categories (name) VALUES (?)"
        try:
            cursor = DatabaseManager.execute_query(query, (name,))
            category_id = cursor.lastrowid
            if category_id is None:
                raise DatabaseException("Failed to get new category ID after insert.")
            CategoryService.clear_cache()
            logger.info(
                "Category created", extra={"category_id": category_id, "name": name}
            )
            event_system.category_added.emit(category_id)
            return category_id
        except Exception as e:
            logger.error(
                "Failed to create category", extra={"error": str(e), "name": name}
            )
            raise DatabaseException(f"Failed to create category: {str(e)}") from e

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_category(category_id: int) -> Category | None:
        category_id = validate_integer(category_id, min_value=1)
        query = "SELECT * FROM categories WHERE id = ?"
        row = DatabaseManager.fetch_one(query, (category_id,))
        if row:
            logger.info("Category retrieved", extra={"category_id": category_id})
            return Category.from_db_row(row)
        logger.warning("Category not found", extra={"category_id": category_id})
        return None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_categories() -> list[Category]:
        query = "SELECT * FROM categories ORDER BY name"
        rows = DatabaseManager.fetch_all(query)
        categories = [Category.from_db_row(row) for row in rows]
        logger.info("All categories retrieved", extra={"count": len(categories)})
        return categories

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(
        NotFoundException, ValidationException, DatabaseException, show_dialog=True
    )
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
            logger.info(
                "Category updated", extra={"category_id": category_id, "new_name": name}
            )
            event_system.category_updated.emit(category_id)
        except Exception as e:
            logger.error(
                "Failed to update category",
                extra={"error": str(e), "category_id": category_id},
            )
            raise DatabaseException(f"Failed to update category: {str(e)}") from e

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
            logger.error(
                "Failed to delete category",
                extra={"error": str(e), "category_id": category_id},
            )
            raise DatabaseException(f"Failed to delete category: {str(e)}") from e

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_categories(search_term: str) -> list[Category]:
        search_term = validate_string(search_term, max_length=50)
        query = """
        SELECT * FROM categories
        WHERE name LIKE ?
        ORDER BY name
        """
        search_pattern = f"%{sanitize_sql(search_term)}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern,))
        categories = [Category.from_db_row(row) for row in rows]
        logger.info(
            "Categories searched",
            extra={"search_term": search_term, "count": len(categories)},
        )
        return categories

    @staticmethod
    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_category_by_name(name: str) -> Category | None:
        name = validate_string(name, min_length=1, max_length=50)
        query = "SELECT * FROM categories WHERE name = ?"
        row = DatabaseManager.fetch_one(query, (name,))
        if row:
            logger.info("Category retrieved by name", extra={"name": name})
            return Category.from_db_row(row)
        logger.warning("Category not found by name", extra={"name": name})
        return None

    @classmethod
    def clear_cache(cls) -> None:
        CategoryService.get_all_categories.cache_clear()
        logger.debug("Category cache cleared")
