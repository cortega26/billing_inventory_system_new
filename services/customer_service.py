from typing import List, Optional, Tuple
from database import DatabaseManager
from models.customer import Customer
from utils.validation.validators import (
    is_valid_9digit_identifier,
    is_valid_3or4digit_identifier,
)
from utils.sanitizers import sanitize_html, sanitize_sql
from utils.decorators import db_operation, handle_exceptions, validate_input
from utils.exceptions import NotFoundException, ValidationException, DatabaseException
from utils.system.logger import logger
from functools import lru_cache

class CustomerService:
    @db_operation(show_dialog=True)
    @validate_input([is_valid_9digit_identifier], "Invalid 9-digit identifier")
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_customer(
        self,
        identifier_9: str,
        identifier_3or4: Optional[str] = None
    ) -> Optional[int]:
        logger.debug(f"Creating customer with identifier_9: {identifier_9}, type: {type(identifier_9)}")
        identifier_9 = str(sanitize_html(identifier_9))
        logger.debug(f"After sanitization, identifier_9: {identifier_9}, type: {type(identifier_9)}")
        if identifier_3or4:
            identifier_3or4 = sanitize_html(identifier_3or4)
            if not is_valid_3or4digit_identifier(identifier_3or4):
                raise ValidationException("Invalid 3 or 4-digit identifier")

        query = "INSERT INTO customers (identifier_9) VALUES (?)"
        try:
            cursor = DatabaseManager.execute_query(query, (identifier_9,))
            customer_id = cursor.lastrowid

            if customer_id is not None and identifier_3or4:
                self.update_identifier_3or4(customer_id, identifier_3or4)

            logger.info("Customer created", customer_id=customer_id, identifier_9=identifier_9)
            self.clear_cache()
            return customer_id
        except Exception as e:
            logger.error("Failed to create customer", error=str(e), identifier_9=identifier_9)
            raise DatabaseException(f"Failed to create customer: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_identifier_3or4(self, customer_id: int, identifier_3or4: Optional[str]) -> None:
        if identifier_3or4 is not None:
            identifier_3or4 = sanitize_html(identifier_3or4)
            if not is_valid_3or4digit_identifier(identifier_3or4):
                raise ValidationException("Invalid 3 or 4-digit identifier")

            delete_query = "DELETE FROM customer_identifiers WHERE customer_id = ?"
            insert_query = "INSERT INTO customer_identifiers (customer_id, identifier_3or4) VALUES (?, ?)"

            try:
                DatabaseManager.execute_query(delete_query, (customer_id,))
                DatabaseManager.execute_query(insert_query, (customer_id, identifier_3or4))
                logger.info("Customer 3or4 identifier updated", customer_id=customer_id, identifier_3or4=identifier_3or4)
            except Exception as e:
                logger.error("Failed to update customer 3or4 identifier", error=str(e), customer_id=customer_id)
                raise DatabaseException(f"Failed to update customer 3or4 identifier: {str(e)}")
        else:
            # If identifier_3or4 is None, remove any existing 3or4 identifier
            delete_query = "DELETE FROM customer_identifiers WHERE customer_id = ?"
            try:
                DatabaseManager.execute_query(delete_query, (customer_id,))
                logger.info("Customer 3or4 identifier removed", customer_id=customer_id)
            except Exception as e:
                logger.error("Failed to remove customer 3or4 identifier", error=str(e), customer_id=customer_id)
                raise DatabaseException(f"Failed to remove customer 3or4 identifier: {str(e)}")

        self.clear_cache()

    @db_operation(show_dialog=True)
    @handle_exceptions(NotFoundException, DatabaseException, show_dialog=True)
    def get_customer(self, customer_id: int) -> Optional[Customer]:
        query = """
        SELECT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE c.id = ?
        """
        row = DatabaseManager.fetch_one(query, (customer_id,))
        if row:
            logger.info("Customer retrieved", customer_id=customer_id)
            return Customer.from_db_row(row)
        else:
            logger.warning("Customer not found", customer_id=customer_id)
            raise NotFoundException(f"Customer with ID {customer_id} not found")

    @lru_cache(maxsize=1)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_customers(self) -> List[Customer]:
        query = """
        SELECT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        """
        rows = DatabaseManager.fetch_all(query)
        customers = [Customer.from_db_row(row) for row in rows]
        logger.info("All customers retrieved", count=len(customers))
        return customers

    @db_operation(show_dialog=True)
    @validate_input([is_valid_9digit_identifier], "Invalid 9-digit identifier")
    @handle_exceptions(NotFoundException, ValidationException, DatabaseException, show_dialog=True)
    def update_customer(
        self,
        customer_id: int,
        identifier_9: str,
        identifier_3or4: Optional[str] = None
    ) -> None:
        identifier_9 = sanitize_html(identifier_9)
        
        query = "UPDATE customers SET identifier_9 = ? WHERE id = ?"
        try:
            DatabaseManager.execute_query(query, (identifier_9, customer_id))
            
            self.update_identifier_3or4(customer_id, identifier_3or4)
            
            logger.info("Customer updated", customer_id=customer_id, identifier_9=identifier_9)
            self.clear_cache()
        except Exception as e:
            logger.error("Failed to update customer", error=str(e), customer_id=customer_id)
            raise DatabaseException(f"Failed to update customer: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_customer(self, customer_id: int) -> None:
        query = "DELETE FROM customers WHERE id = ?"
        try:
            DatabaseManager.execute_query(query, (customer_id,))
            DatabaseManager.execute_query("DELETE FROM customer_identifiers WHERE customer_id = ?", (customer_id,))
            logger.info("Customer deleted", customer_id=customer_id)
            self.clear_cache()
        except Exception as e:
            logger.error("Failed to delete customer", error=str(e), customer_id=customer_id)
            raise DatabaseException(f"Failed to delete customer: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_customer_by_identifier_9(self, identifier_9: str) -> Optional[Customer]:
        query = """
        SELECT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE c.identifier_9 = ?
        """
        row = DatabaseManager.fetch_one(query, (identifier_9,))
        if row:
            logger.info("Customer retrieved by identifier_9", identifier_9=identifier_9)
            return Customer.from_db_row(row)
        else:
            logger.warning("Customer not found by identifier_9", identifier_9=identifier_9)
            return None

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_customers_by_identifier_3or4(self, identifier_3or4: str) -> List[Customer]:
        query = """
        SELECT c.*, ci.identifier_3or4
        FROM customers c
        JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE ci.identifier_3or4 = ?
        """
        rows = DatabaseManager.fetch_all(query, (identifier_3or4,))
        customers = [Customer.from_db_row(row) for row in rows]
        logger.info("Customers retrieved by identifier_3or4", identifier_3or4=identifier_3or4, count=len(customers))
        return customers

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_customer_stats(self, customer_id: int) -> Tuple[int, float]:
        query = """
            SELECT COUNT(*) as total_purchases, COALESCE(SUM(total_amount), 0) as total_amount
            FROM sales
            WHERE customer_id = ?
        """
        result = DatabaseManager.fetch_one(query, (customer_id,))
        if result:
            logger.info("Customer stats retrieved", customer_id=customer_id)
            return result["total_purchases"], result["total_amount"]
        else:
            logger.warning("Customer stats not found", customer_id=customer_id)
            return 0, 0

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_customers(self, search_term: str) -> List[Customer]:
        query = """
        SELECT DISTINCT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE c.identifier_9 LIKE ? OR ci.identifier_3or4 LIKE ?
        """
        search_pattern = f"%{sanitize_sql(search_term)}%"
        rows = DatabaseManager.fetch_all(query, (search_pattern, search_pattern))
        customers = [Customer.from_db_row(row) for row in rows]
        logger.info("Customers searched", search_term=search_term, count=len(customers))
        return customers

    def clear_cache(self):
        self.get_all_customers.cache_clear()
        logger.debug("Customer cache cleared")
