from typing import List, Optional, Tuple
from database import DatabaseManager
from models.customer import Customer
from utils.validators import validate_9digit_identifier, validate_3or4digit_identifier
from utils.logger import logger
from functools import lru_cache

class CustomerService:
    @staticmethod
    def create_customer(identifier_9: str, identifier_3or4: Optional[str] = None) -> Optional[int]:
        try:
            logger.debug(f"Creating customer with identifier_9: {identifier_9}, identifier_3or4: {identifier_3or4}")
            validate_9digit_identifier(identifier_9)
            
            query = 'INSERT INTO customers (identifier_9) VALUES (?)'
            cursor = DatabaseManager.execute_query(query, (identifier_9,))
            customer_id = cursor.lastrowid

            if customer_id is not None and identifier_3or4:
                CustomerService.update_identifier_3or4(customer_id, identifier_3or4)

            logger.debug(f"Created customer with ID: {customer_id}")
            CustomerService.clear_cache()
            return customer_id
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            raise

    @staticmethod
    def update_identifier_3or4(customer_id: int, identifier_3or4: str) -> None:
        try:
            logger.debug(f"Updating identifier_3or4: {identifier_3or4} for customer ID: {customer_id}")
            validate_3or4digit_identifier(identifier_3or4)
            
            # First, delete any existing identifiers for this customer
            delete_query = 'DELETE FROM customer_identifiers WHERE customer_id = ?'
            DatabaseManager.execute_query(delete_query, (customer_id,))
            
            # Then, insert the new identifier
            insert_query = 'INSERT INTO customer_identifiers (customer_id, identifier_3or4) VALUES (?, ?)'
            DatabaseManager.execute_query(insert_query, (customer_id, identifier_3or4))
            
            logger.debug(f"Updated identifier_3or4 for customer ID: {customer_id}")
            CustomerService.clear_cache()
        except Exception as e:
            logger.error(f"Error updating identifier_3or4: {str(e)}")
            raise

    @staticmethod
    def get_customer(customer_id: int) -> Optional[Customer]:
        try:
            logger.debug(f"Getting customer with ID: {customer_id}")
            query = '''
            SELECT c.*, ci.identifier_3or4
            FROM customers c
            LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
            WHERE c.id = ?
            '''
            row = DatabaseManager.fetch_one(query, (customer_id,))
            if row:
                customer = Customer.from_db_row(row)
                customer.identifier_3or4 = row['identifier_3or4']
                logger.debug(f"Retrieved customer: {customer}")
                return customer
            logger.debug(f"No customer found with ID: {customer_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting customer: {str(e)}")
            raise

    @staticmethod
    @lru_cache(maxsize=1)
    def get_all_customers() -> List[Customer]:
        try:
            logger.debug("Getting all customers")
            query = '''
            SELECT c.*, ci.identifier_3or4
            FROM customers c
            LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
            '''
            rows = DatabaseManager.fetch_all(query)
            customers = [Customer.from_db_row(row) for row in rows]
            for customer, row in zip(customers, rows):
                customer.identifier_3or4 = row['identifier_3or4']
            logger.debug(f"Retrieved {len(customers)} customers")
            return customers
        except Exception as e:
            logger.error(f"Error getting all customers: {str(e)}")
            raise

    @staticmethod
    def update_customer(customer_id: int, identifier_9: str, identifier_3or4: Optional[str] = None) -> None:
        try:
            logger.debug(f"Updating customer with ID: {customer_id}, identifier_9: {identifier_9}, identifier_3or4: {identifier_3or4}")
            validate_9digit_identifier(identifier_9)
            
            query = 'UPDATE customers SET identifier_9 = ? WHERE id = ?'
            DatabaseManager.execute_query(query, (identifier_9, customer_id))
            
            if identifier_3or4 is not None:
                CustomerService.update_identifier_3or4(customer_id, identifier_3or4)
            logger.debug(f"Customer updated successfully")
            CustomerService.clear_cache()
        except Exception as e:
            logger.error(f"Error updating customer: {str(e)}")
            raise

    @staticmethod
    def delete_customer(customer_id: int) -> None:
        try:
            logger.debug(f"Deleting customer with ID: {customer_id}")
            query = 'DELETE FROM customers WHERE id = ?'
            DatabaseManager.execute_query(query, (customer_id,))
            
            query = 'DELETE FROM customer_identifiers WHERE customer_id = ?'
            DatabaseManager.execute_query(query, (customer_id,))
            
            logger.info(f"Deleted customer with ID: {customer_id}")
            CustomerService.clear_cache()
        except Exception as e:
            logger.error(f"Error deleting customer: {str(e)}")
            raise

    @staticmethod
    def get_customer_by_identifier_9(identifier_9: str) -> Optional[Customer]:
        try:
            logger.debug(f"Getting customer by identifier_9: {identifier_9}")
            query = '''
            SELECT c.*, ci.identifier_3or4
            FROM customers c
            LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
            WHERE c.identifier_9 = ?
            '''
            row = DatabaseManager.fetch_one(query, (identifier_9,))
            if row:
                customer = Customer.from_db_row(row)
                customer.identifier_3or4 = row['identifier_3or4']
                return customer
            return None
        except Exception as e:
            logger.error(f"Error getting customer by identifier_9: {str(e)}")
            raise

    @staticmethod
    def get_customers_by_identifier_3or4(identifier_3or4: str) -> List[Customer]:
        try:
            logger.debug(f"Getting customers by identifier_3or4: {identifier_3or4}")
            query = '''
            SELECT c.*, ci.identifier_3or4
            FROM customers c
            JOIN customer_identifiers ci ON c.id = ci.customer_id
            WHERE ci.identifier_3or4 = ?
            '''
            rows = DatabaseManager.fetch_all(query, (identifier_3or4,))
            customers = [Customer.from_db_row(row) for row in rows]
            for customer, row in zip(customers, rows):
                customer.identifier_3or4 = row['identifier_3or4']
            return customers
        except Exception as e:
            logger.error(f"Error getting customers by identifier_3or4: {str(e)}")
            raise

    @staticmethod
    def get_customer_stats(customer_id: int) -> Tuple[int, float]:
        try:
            logger.debug(f"Getting stats for customer ID: {customer_id}")
            query = '''
                SELECT COUNT(*) as total_purchases, COALESCE(SUM(total_amount), 0) as total_amount
                FROM sales
                WHERE customer_id = ?
            '''
            result = DatabaseManager.fetch_one(query, (customer_id,))
            if result:
                return result['total_purchases'], result['total_amount']
            return 0, 0
        except Exception as e:
            logger.error(f"Error getting customer stats: {str(e)}")
            raise

    @staticmethod
    def search_customers(search_term: str) -> List[Customer]:
        try:
            logger.debug(f"Searching customers with term: {search_term}")
            query = '''
            SELECT DISTINCT c.*, ci.identifier_3or4
            FROM customers c
            LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
            WHERE c.identifier_9 LIKE ? OR ci.identifier_3or4 LIKE ?
            '''
            search_pattern = f"%{search_term}%"
            rows = DatabaseManager.fetch_all(query, (search_pattern, search_pattern))
            customers = [Customer.from_db_row(row) for row in rows]
            for customer, row in zip(customers, rows):
                customer.identifier_3or4 = row['identifier_3or4']
            return customers
        except Exception as e:
            logger.error(f"Error searching customers: {str(e)}")
            raise

    @staticmethod
    def clear_cache():
        CustomerService.get_all_customers.cache_clear()
