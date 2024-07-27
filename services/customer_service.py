from database import execute_query, fetch_one, fetch_all
from models.customer import Customer

class CustomerService:
    @staticmethod
    def create_customer(identifier_9, identifier_4=None):
        query = 'INSERT INTO customers (identifier_9, identifier_4) VALUES (?, ?)'
        cursor = execute_query(query, (identifier_9, identifier_4))
        return cursor.lastrowid

    @staticmethod
    def get_customer(customer_id):
        query = 'SELECT * FROM customers WHERE id = ?'
        row = fetch_one(query, (customer_id,))
        return Customer.from_row(row) if row else None

    @staticmethod
    def get_all_customers():
        query = 'SELECT * FROM customers'
        rows = fetch_all(query)
        return [Customer.from_row(row) for row in rows]

    @staticmethod
    def update_customer(customer_id, identifier_9, identifier_4=None):
        query = 'UPDATE customers SET identifier_9 = ?, identifier_4 = ? WHERE id = ?'
        execute_query(query, (identifier_9, identifier_4, customer_id))

    @staticmethod
    def delete_customer(customer_id):
        query = 'DELETE FROM customers WHERE id = ?'
        execute_query(query, (customer_id,))

    @staticmethod
    def update_identifier_4(identifier_4):
        query = 'UPDATE customers SET identifier_4 = ? WHERE identifier_4 IS NULL'
        execute_query(query, (identifier_4,))

    @staticmethod
    def get_customer_by_identifier_9(identifier_9):
        query = 'SELECT * FROM customers WHERE identifier_9 = ?'
        row = fetch_one(query, (identifier_9,))
        return Customer.from_row(row) if row else None