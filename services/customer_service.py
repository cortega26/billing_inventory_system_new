from typing import List, Optional, Tuple
from database import DatabaseManager
from models.customer import Customer, CustomerIdentifier
from utils.validators import validate_9digit_identifier, validate_3or4digit_identifier
from utils.logger import logger

class CustomerService:
    @staticmethod
    def create_customer(identifier_9: str, identifier_3or4: Optional[str] = None) -> Optional[int]:
        logger.debug(f"Creating customer with identifier_9: {identifier_9}, identifier_3or4: {identifier_3or4}")
        validate_9digit_identifier(identifier_9)
        
        query = 'INSERT INTO customers (identifier_9) VALUES (?)'
        cursor = DatabaseManager.execute_query(query, (identifier_9,))
        customer_id = cursor.lastrowid

        if customer_id is not None and identifier_3or4:
            CustomerService.add_identifier_3or4(customer_id, identifier_3or4)

        logger.debug(f"Created customer with ID: {customer_id}")
        return customer_id

    @staticmethod
    def add_identifier_3or4(customer_id: int, identifier_3or4: str) -> None:
        logger.debug(f"Adding identifier_3or4: {identifier_3or4} to customer ID: {customer_id}")
        validate_3or4digit_identifier(identifier_3or4)
        query = 'INSERT INTO customer_identifiers (customer_id, identifier_3or4) VALUES (?, ?)'
        DatabaseManager.execute_query(query, (customer_id, identifier_3or4))

    @staticmethod
    def get_customer(customer_id: int) -> Optional[Customer]:
        logger.debug(f"Getting customer with ID: {customer_id}")
        query = 'SELECT * FROM customers WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (customer_id,))
        if row:
            customer = Customer.from_row(row)
            customer.identifiers_3or4 = CustomerService.get_identifiers_3or4(customer_id)
            logger.debug(f"Retrieved customer: {customer}")
            return customer
        logger.debug(f"No customer found with ID: {customer_id}")
        return None

    @staticmethod
    def get_identifiers_3or4(customer_id: int) -> List[CustomerIdentifier]:
        logger.debug(f"Getting identifiers_3or4 for customer ID: {customer_id}")
        query = 'SELECT * FROM customer_identifiers WHERE customer_id = ?'
        rows = DatabaseManager.fetch_all(query, (customer_id,))
        return [CustomerIdentifier(row['id'], row['customer_id'], row['identifier_3or4']) for row in rows]

    @staticmethod
    def get_all_customers() -> List[Customer]:
        logger.debug("Getting all customers")
        query = 'SELECT * FROM customers'
        rows = DatabaseManager.fetch_all(query)
        customers = [Customer.from_row(row) for row in rows]
        for customer in customers:
            customer.identifiers_3or4 = CustomerService.get_identifiers_3or4(customer.id)
        logger.debug(f"Retrieved {len(customers)} customers")
        return customers

    @staticmethod
    def update_customer(customer_id: int, identifier_9: str, identifier_3or4: Optional[str] = None) -> None:
        logger.debug(f"Updating customer with ID: {customer_id}, identifier_9: {identifier_9}, identifier_3or4: {identifier_3or4}")
        validate_9digit_identifier(identifier_9)
        
        query = 'UPDATE customers SET identifier_9 = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (identifier_9, customer_id))
        
        if identifier_3or4:
            CustomerService.add_identifier_3or4(customer_id, identifier_3or4)
        logger.debug(f"Customer updated successfully")

    @staticmethod
    def delete_customer(customer_id: int) -> None:
        logger.debug(f"Deleting customer with ID: {customer_id}")
        query = 'DELETE FROM customers WHERE id = ?'
        DatabaseManager.execute_query(query, (customer_id,))
        
        query = 'DELETE FROM customer_identifiers WHERE customer_id = ?'
        DatabaseManager.execute_query(query, (customer_id,))

    @staticmethod
    def get_customer_by_identifier_9(identifier_9: str) -> Optional[Customer]:
        logger.debug(f"Getting customer by identifier_9: {identifier_9}")
        query = 'SELECT * FROM customers WHERE identifier_9 = ?'
        row = DatabaseManager.fetch_one(query, (identifier_9,))
        if row:
            customer = Customer.from_row(row)
            customer.identifiers_3or4 = CustomerService.get_identifiers_3or4(customer.id)
            return customer
        return None

    @staticmethod
    def get_customers_by_identifier_3or4(identifier_3or4: str) -> List[Customer]:
        logger.debug(f"Getting customers by identifier_3or4: {identifier_3or4}")
        query = '''
        SELECT c.* FROM customers c
        JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE ci.identifier_3or4 = ?
        '''
        rows = DatabaseManager.fetch_all(query, (identifier_3or4,))
        customers = [Customer.from_row(row) for row in rows]
        for customer in customers:
            customer.identifiers_3or4 = CustomerService.get_identifiers_3or4(customer.id)
        return customers

    @staticmethod
    def get_customer_stats(customer_id: int) -> Tuple[int, int]:
        logger.debug(f"Getting stats for customer ID: {customer_id}")
        query = '''
            SELECT COUNT(*) as total_purchases, COALESCE(SUM(total_amount), 0) as total_amount
            FROM sales
            WHERE customer_id = ?
        '''
        row = DatabaseManager.fetch_one(query, (customer_id,))
        return row['total_purchases'], row['total_amount']