from typing import List, Optional
from database import DatabaseManager
from models.category import Category
from utils.validators import validate_string
from utils.logger import logger

class CategoryService:
    @staticmethod
    def create_category(name: str) -> Optional[int]:
        logger.debug(f"Creating category with name: {name}")
        name = validate_string(name, "Category name", max_length=50)
        
        query = 'INSERT INTO categories (name) VALUES (?)'
        cursor = DatabaseManager.execute_query(query, (name,))
        category_id = cursor.lastrowid
        logger.debug(f"Created category with ID: {category_id}")
        return category_id if category_id is not None else None

    @staticmethod
    def get_category(category_id: int) -> Optional[Category]:
        logger.debug(f"Getting category with ID: {category_id}")
        query = 'SELECT * FROM categories WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (category_id,))
        if row:
            category = Category.from_db_row(row)
            logger.debug(f"Retrieved category: {category}")
            return category
        logger.debug(f"No category found with ID: {category_id}")
        return None

    @staticmethod
    def get_all_categories() -> List[Category]:
        logger.debug("Getting all categories")
        query = 'SELECT * FROM categories ORDER BY name'
        rows = DatabaseManager.fetch_all(query)
        categories = [Category.from_db_row(row) for row in rows]
        logger.debug(f"Retrieved {len(categories)} categories")
        return categories

    @staticmethod
    def update_category(category_id: int, name: str) -> None:
        logger.debug(f"Updating category with ID: {category_id}, name: {name}")
        name = validate_string(name, "Category name", max_length=50)
        query = 'UPDATE categories SET name = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (name, category_id))
        logger.debug(f"Category updated successfully")

    @staticmethod
    def delete_category(category_id: int) -> None:
        logger.debug(f"Deleting category with ID: {category_id}")
        query = 'DELETE FROM categories WHERE id = ?'
        DatabaseManager.execute_query(query, (category_id,))
        logger.info(f"Deleted category with ID: {category_id}")

    @staticmethod
    def search_categories(search_term: str) -> List[Category]:
        logger.debug(f"Searching categories with term: {search_term}")
        query = '''
        SELECT * FROM categories
        WHERE name LIKE ?
        ORDER BY name
        '''
        search_pattern = f"%{search_term}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern,))
        categories = [Category.from_db_row(row) for row in rows]
        logger.debug(f"Found {len(categories)} categories matching search term: {search_term}")
        return categories