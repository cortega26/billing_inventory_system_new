from typing import List, Dict, Any, Optional, Tuple
from database.database_manager import DatabaseManager
from models.customer import Customer
from utils.validation.validators import (
    validate_9digit_identifier as validate_identifier_9,
    validate_3or4digit_identifier as validate_identifier_3or4,
    validate_integer,
    validate_string
)
from utils.sanitizers import sanitize_html, sanitize_sql
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import NotFoundException, ValidationException, DatabaseException
from utils.system.logger import logger
from utils.system.event_system import event_system
from functools import lru_cache

class CustomerService:
    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def create_customer(
        self,
        identifier_9: str,
        name: Optional[str] = None,
        identifier_3or4: Optional[str] = None
    ) -> Optional[int]:
        """
        Create a new customer.

        Args:
            identifier_9 (str): The 9-digit identifier.
            name (Optional[str]): The customer's name.
            identifier_3or4 (Optional[str]): The 3 or 4-digit identifier.

        Returns:
            Optional[int]: The ID of the created customer.

        Raises:
            ValidationException: If validation fails.
            DatabaseException: If database operation fails.
        """
        logger.debug(f"Creating customer with identifier_9: {identifier_9}")
        identifier_9 = validate_identifier_9(sanitize_html(str(identifier_9)))
        
        if name is not None:
            temp_customer = Customer(id=0, identifier_9="000000000", name=name)
            name = temp_customer.name  # This will be the normalized version
        
        if identifier_3or4:
            identifier_3or4 = validate_identifier_3or4(sanitize_html(identifier_3or4))

        query = "INSERT INTO customers (identifier_9, name) VALUES (?, ?)"
        params = (identifier_9, name)
        try:
            cursor = DatabaseManager.execute_query(query, params)
            customer_id = cursor.lastrowid

            if customer_id is not None and identifier_3or4:
                self.update_identifier_3or4(customer_id, identifier_3or4)

            self.clear_cache()
            logger.info("Customer created", extra={
                "customer_id": customer_id,
                "identifier_9": identifier_9
            })
            event_system.customer_added.emit(customer_id)
            return customer_id
        except Exception as e:
            logger.error("Failed to create customer", extra={
                "error": str(e),
                "identifier_9": identifier_9
            })
            raise DatabaseException(f"Failed to create customer: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_identifier_3or4(self, customer_id: int, identifier_3or4: Optional[str]) -> None:
        """
        Update the 3 or 4-digit identifier for a customer.

        Args:
            customer_id (int): The customer ID.
            identifier_3or4 (Optional[str]): The new identifier.

        Raises:
            ValidationException: If validation fails.
            DatabaseException: If database operation fails.
        """
        customer_id = validate_integer(customer_id, min_value=1)
        if identifier_3or4 is not None:
            identifier_3or4 = validate_identifier_3or4(sanitize_html(identifier_3or4))

        delete_query = "DELETE FROM customer_identifiers WHERE customer_id = ?"
        insert_query = "INSERT INTO customer_identifiers (customer_id, identifier_3or4) VALUES (?, ?)"

        try:
            DatabaseManager.execute_query(delete_query, (customer_id,))
            if identifier_3or4:
                DatabaseManager.execute_query(insert_query, (customer_id, identifier_3or4))
            logger.info("Customer 3or4 identifier updated", extra={
                "customer_id": customer_id,
                "identifier_3or4": identifier_3or4
            })
        except Exception as e:
            logger.error("Failed to update customer 3or4 identifier", extra={
                "error": str(e),
                "customer_id": customer_id
            })
            raise DatabaseException(f"Failed to update customer 3or4 identifier: {str(e)}")

        self.clear_cache()
        event_system.customer_updated.emit(customer_id)

    @db_operation(show_dialog=True)
    def get_customer(self, customer_id: int) -> Optional[Customer]:
        """
        Get a customer by ID.

        Args:
            customer_id (int): The customer ID.

        Returns:
            Optional[Customer]: The customer if found.

        Raises:
            NotFoundException: If customer not found.
            DatabaseException: If database operation fails.
        """
        customer_id = validate_integer(customer_id, min_value=1)
        query = """
        SELECT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE c.id = ?
        """
        row = DatabaseManager.fetch_one(query, (customer_id,))
        if not row:
            logger.warning(f"Customer not found", extra={"customer_id": customer_id})
            return None
        logger.debug("Customer retrieved", extra={"customer_id": customer_id})
        return Customer.from_db_row(row)

    @lru_cache(maxsize=100)
    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_all_customers(self) -> List[Customer]:
        """
        Get all customers.

        Returns:
            List[Customer]: List of all customers.

        Raises:
            DatabaseException: If database operation fails.
        """
        query = """
        SELECT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        ORDER BY c.identifier_9
        """
        try:
            # *** new log statement ***
            logger.debug(f"[get_all_customers] Executing SQL: {query}")

            rows = DatabaseManager.fetch_all(query)

            # *** new log statement ***
            logger.debug(f"[get_all_customers] Fetched {len(rows)} rows from DB. Example row: {rows[0] if rows else 'no rows'}")

            customers = [Customer.from_db_row(row) for row in rows]

            # *** new log statement ***
            for i, cust in enumerate(customers[:5]):  # just log first 5 for brevity
                logger.debug(f"[get_all_customers] Customer #{i} => ID={cust.id}...")

            logger.info("All customers retrieved", extra={"count": len(customers)})
            return customers
        except Exception as e:
            logger.error(f"Error fetching all customers: {str(e)}")
            raise DatabaseException(f"Failed to fetch customers: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, show_dialog=True)
    def update_customer(self, customer_id: int, **kwargs):
        """Update customer details by ID."""
        logger.debug(f"[update_customer] Starting with kwargs: {kwargs}")
        
        try:
            customer_id = validate_integer(customer_id, min_value=1)
            customer_updates = {}
            
            # Debug log the validation steps
            logger.debug("[update_customer] Starting field validation")
            
            if 'name' in kwargs:
                logger.debug(f"[update_customer] Validating name: {kwargs['name']}")
                name = kwargs['name']
                if name is not None:
                    validate_string(name, max_length=50)
                customer_updates['name'] = name
                
            if 'identifier_9' in kwargs:
                logger.debug(f"[update_customer] Validating identifier_9: {kwargs['identifier_9']}")
                identifier_9 = validate_identifier_9(kwargs['identifier_9'])
                customer_updates['identifier_9'] = identifier_9

            # Log the SQL query before execution
            if customer_updates:
                update_fields = []
                params = []
                for key, value in customer_updates.items():
                    update_fields.append(f"{key} = ?")
                    params.append(value)
                
                query = """
                    UPDATE customers 
                    SET {} 
                    WHERE id = ?
                """.format(", ".join(update_fields))
                params.append(customer_id)
                
                # Debug log the actual SQL and parameters
                logger.debug(f"[update_customer] Executing SQL: {query}")
                logger.debug(f"[update_customer] With parameters: {params}")
                
                DatabaseManager.execute_query(query, tuple(params))

            # Handle identifier_3or4 separately
            if 'identifier_3or4' in kwargs:
                logger.debug(f"[update_customer] Handling identifier_3or4: {kwargs['identifier_3or4']}")
                identifier_3or4 = kwargs['identifier_3or4']
                if identifier_3or4:
                    identifier_3or4 = validate_identifier_3or4(identifier_3or4)
                self.update_identifier_3or4(customer_id, identifier_3or4)

            logger.debug("[update_customer] Update completed successfully")
            self.clear_cache()
            
        except Exception as e:
            logger.error(
                f"[update_customer] Error: {str(e)}", 
                extra={"exc_info": True}
            )
            raise DatabaseException(f"Failed to update customer: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def delete_customer(self, customer_id: int) -> None:
        """
        Delete a customer.

        Args:
            customer_id (int): The customer ID.

        Raises:
            DatabaseException: If database operation fails.
            NotFoundException: If customer not found.
        """
        customer_id = validate_integer(customer_id, min_value=1)
        query = "DELETE FROM customers WHERE id = ?"
        try:
            cursor = DatabaseManager.execute_query(query, (customer_id,))
            if cursor.rowcount == 0:
                raise NotFoundException(f"Customer with ID {customer_id} not found")
            DatabaseManager.execute_query(
                "DELETE FROM customer_identifiers WHERE customer_id = ?",
                (customer_id,)
            )
            logger.info("Customer deleted", extra={"customer_id": customer_id})
            self.clear_cache()
            event_system.customer_deleted.emit(customer_id)
        except Exception as e:
            logger.error("Failed to delete customer", extra={
                "error": str(e),
                "customer_id": customer_id
            })
            raise DatabaseException(f"Failed to delete customer: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_customer_by_identifier_9(self, identifier_9: str) -> Optional[Customer]:
        """
        Get a customer by their 9-digit identifier.

        Args:
            identifier_9 (str): The 9-digit identifier.

        Returns:
            Optional[Customer]: The customer if found.

        Raises:
            DatabaseException: If database operation fails.
        """
        identifier_9 = validate_identifier_9(identifier_9)
        query = """
        SELECT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE c.identifier_9 = ?
        """
        row = DatabaseManager.fetch_one(query, (identifier_9,))
        if row:
            logger.info("Customer retrieved by identifier_9", extra={"identifier_9": identifier_9})
            return Customer.from_db_row(row)
        else:
            logger.warning("Customer not found by identifier_9", extra={"identifier_9": identifier_9})
            return None

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_customers_by_identifier_3or4(self, identifier_3or4: str) -> List[Customer]:
        """
        Get customers by their 3 or 4-digit identifier.
        Returns a list of unique customers based on identifier_9.

        Args:
            identifier_3or4 (str): The 3 or 4-digit identifier.

        Returns:
            List[Customer]: List of unique matching customers.

        Raises:
            DatabaseException: If database operation fails.
        """
        identifier_3or4 = validate_identifier_3or4(identifier_3or4)
        query = """
        SELECT DISTINCT c.*, ci.identifier_3or4
        FROM customers c
        JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE ci.identifier_3or4 = ?
        ORDER BY c.identifier_9
        """
        try:
            rows = DatabaseManager.fetch_all(query, (identifier_3or4,))
            customers = [Customer.from_db_row(row) for row in rows]
            
            # Remove duplicates based on identifier_9
            unique_customers = []
            seen_phones = set()
            for customer in customers:
                if customer.identifier_9 not in seen_phones:
                    unique_customers.append(customer)
                    seen_phones.add(customer.identifier_9)
                else:
                    logger.warning(f"Duplicate customer found with phone {customer.identifier_9} for department {identifier_3or4}")
            
            logger.info(f"Retrieved {len(unique_customers)} unique customers by identifier_3or4", extra={
                "identifier_3or4": identifier_3or4,
                "total_found": len(customers),
                "unique_count": len(unique_customers)
            })
            
            return unique_customers
            
        except Exception as e:
            logger.error(f"Error retrieving customers by identifier_3or4: {str(e)}")
            raise DatabaseException(f"Failed to retrieve customers: {str(e)}")

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def get_customer_stats(self, customer_id: int) -> Tuple[int, int]:
        """
        Get customer statistics.

        Args:
            customer_id (int): The customer ID.

        Returns:
            Tuple[int, int]: Total purchases and total amount.

        Raises:
            DatabaseException: If database operation fails.
        """
        customer_id = validate_integer(customer_id, min_value=1)
        query = """
            SELECT COUNT(*) as total_purchases,
                   COALESCE(SUM(total_amount), 0) as total_amount
            FROM sales
            WHERE customer_id = ?
        """
        result = DatabaseManager.fetch_one(query, (customer_id,))
        if result:
            logger.info("Customer stats retrieved", extra={"customer_id": customer_id})
            return result["total_purchases"], result["total_amount"]
        else:
            logger.warning("Customer stats not found", extra={"customer_id": customer_id})
            return 0, 0

    @db_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, show_dialog=True)
    def search_customers(self, search_term: str) -> List[Customer]:
        """
        Search customers by name or identifier.

        Args:
            search_term (str): Search term.

        Returns:
            List[Customer]: List of matching customers.

        Raises:
            DatabaseException: If database operation fails.
        """
        search_term = validate_string(search_term, max_length=50)
        query = """
        SELECT DISTINCT c.*, ci.identifier_3or4
        FROM customers c
        LEFT JOIN customer_identifiers ci ON c.id = ci.customer_id
        WHERE c.identifier_9 LIKE ? 
           OR ci.identifier_3or4 LIKE ?
           OR (c.name IS NOT NULL AND LOWER(c.name) LIKE LOWER(?))
        """
        # For name search, only match from start
        name_pattern = f"{sanitize_sql(search_term)}%"
        # For identifiers, match anywhere
        id_pattern = f"%{sanitize_sql(search_term)}%"
        
        rows = DatabaseManager.fetch_all(query, (id_pattern, id_pattern, name_pattern))
        customers = [Customer.from_db_row(row) for row in rows]
        logger.info("Customers searched", extra={
            "search_term": search_term,
            "count": len(customers)
        })
        return customers

    def clear_cache(self):
        """Clear the customer cache."""
        self.get_all_customers.cache_clear()
        logger.debug("Customer cache cleared")

    @db_operation(show_dialog=True)
    def get_customer_purchase_history(self, customer_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get customer purchase history.

        Args:
            customer_id (int): The customer ID.
            limit (int): Maximum number of records to return.

        Returns:
            List[Dict[str, Any]]: List of purchase records.

        Raises:
            DatabaseException: If database operation fails.
        """
        customer_id = validate_integer(customer_id, min_value=1)
        limit = validate_integer(limit, min_value=1)
        query = """
        SELECT s.id as sale_id, s.date, s.total_amount, s.total_profit, s.receipt_id,
               COUNT(si.id) as item_count
        FROM sales s
        LEFT JOIN sale_items si ON s.id = si.sale_id
        WHERE s.customer_id = ?
        GROUP BY s.id
        ORDER BY s.date DESC
        LIMIT ?
        """
        rows = DatabaseManager.fetch_all(query, (customer_id, limit))
        logger.info("Customer purchase history retrieved", extra={
            "customer_id": customer_id,
            "count": len(rows)
        })
        return rows
