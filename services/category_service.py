from typing import List, Optional
from database import DatabaseManager
from models.category import Category
from utils.validation.validators import validate_string
from utils.decorators import db_operation, validate_input
from functools import lru_cache

class CategoryService:
    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def create_category(name: str) -> Optional[int]:
        name = validate_string(name, "Category name", max_length=50)
        query = 'INSERT INTO categories (name) VALUES (?)'
        cursor = DatabaseManager.execute_query(query, (name,))
        category_id = cursor.lastrowid
        CategoryService.clear_cache()
        return category_id

    @staticmethod
    @db_operation(show_dialog=True)
    def get_category(category_id: int) -> Optional[Category]:
        query = 'SELECT * FROM categories WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (category_id,))
        return Category.from_db_row(row) if row else None

    @staticmethod
    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    def get_all_categories() -> List[Category]:
        query = 'SELECT * FROM categories ORDER BY name'
        rows = DatabaseManager.fetch_all(query)
        return [Category.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    @validate_input(show_dialog=True)
    def update_category(category_id: int, name: str) -> None:
        name = validate_string(name, "Category name", max_length=50)
        query = 'UPDATE categories SET name = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (name, category_id))
        CategoryService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def delete_category(category_id: int) -> None:
        query = 'DELETE FROM categories WHERE id = ?'
        DatabaseManager.execute_query(query, (category_id,))
        CategoryService.clear_cache()

    @staticmethod
    @db_operation(show_dialog=True)
    def search_categories(search_term: str) -> List[Category]:
        query = '''
        SELECT * FROM categories
        WHERE name LIKE ?
        ORDER BY name
        '''
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern,))
        return [Category.from_db_row(row) for row in rows]

    @staticmethod
    @db_operation(show_dialog=True)
    def get_category_by_name(name: str) -> Optional[Category]:
        query = 'SELECT * FROM categories WHERE name = ?'
        row = DatabaseManager.fetch_one(query, (name,))
        return Category.from_db_row(row) if row else None

    @staticmethod
    def clear_cache():
        CategoryService.get_all_categories.cache_clear()
