from typing import List, Optional, Tuple
from database import DatabaseManager
from models.customer import Customer

class CustomerService:
    @staticmethod
    def create_customer(identifier_9: str, identifier_4: Optional[str] = None) -> Optional[int]:
        query = 'INSERT INTO customers (identifier_9, identifier_4) VALUES (?, ?)'
        cursor = DatabaseManager.execute_query(query, (identifier_9, identifier_4))
        return cursor.lastrowid if cursor.lastrowid is not None else None

    @staticmethod
    def get_customer(customer_id: int) -> Optional[Customer]:
        query = 'SELECT * FROM customers WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (customer_id,))
        return Customer.from_row(row) if row else None

    @staticmethod
    def get_all_customers() -> List[Customer]:
        query = 'SELECT * FROM customers'
        rows = DatabaseManager.fetch_all(query)
        return [Customer.from_row(row) for row in rows]

    @staticmethod
    def update_customer(customer_id: int, identifier_9: str, identifier_4: Optional[str] = None) -> None:
        query = 'UPDATE customers SET identifier_9 = ?, identifier_4 = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (identifier_9, identifier_4, customer_id))

    @staticmethod
    def delete_customer(customer_id: int) -> None:
        query = 'DELETE FROM customers WHERE id = ?'
        DatabaseManager.execute_query(query, (customer_id,))

    @staticmethod
    def update_identifier_4(identifier_4: str) -> None:
        query = 'UPDATE customers SET identifier_4 = ? WHERE identifier_4 IS NULL'
        DatabaseManager.execute_query(query, (identifier_4,))

    @staticmethod
    def get_customer_by_identifier_9(identifier_9: str) -> Optional[Customer]:
        query = 'SELECT * FROM customers WHERE identifier_9 = ?'
        row = DatabaseManager.fetch_one(query, (identifier_9,))
        return Customer.from_row(row) if row else None

    @staticmethod
    def get_customers_by_identifier_4(identifier_4: str) -> List[Customer]:
        query = 'SELECT * FROM customers WHERE identifier_4 = ?'
        rows = DatabaseManager.fetch_all(query, (identifier_4,))
        return [Customer.from_row(row) for row in rows]

    @staticmethod
    def get_customer_stats(customer_id: int) -> Tuple[int, int]:
        query = '''
            SELECT COUNT(*) as total_purchases, COALESCE(SUM(total_amount), 0) as total_amount
            FROM sales
            WHERE customer_id = ?
        '''
        row = DatabaseManager.fetch_one(query, (customer_id,))
        return row['total_purchases'], row['total_amount']