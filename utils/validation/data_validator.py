import sqlite3
from typing import Tuple, List, Dict, Any
from database import DatabaseManager
from utils.exceptions import DatabaseException
from utils.system.logger import logger
from utils.decorators import db_operation


class DataValidationService:
    """Service for validating data integrity across the application."""

    @staticmethod
    @db_operation(show_dialog=True)
    def diagnose_sales_data() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Diagnose sales data for inconsistencies.
        Returns tuple of (invalid_sales, orphaned_items)
        """
        logger.info("Starting sales data diagnosis")

        invalid_sales = []
        orphaned_items = []

        # Check for sales with future dates
        future_date_query = """
            SELECT s.*, GROUP_CONCAT(si.id) as item_ids
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE date > date('now')
            GROUP BY s.id
        """

        # Check for orphaned sale items
        orphaned_items_query = """
            SELECT si.*
            FROM sale_items si
            LEFT JOIN sales s ON si.sale_id = s.id
            WHERE s.id IS NULL
        """

        try:
            with DatabaseManager.get_db_connection() as conn:
                # Check future dates
                cursor = conn.execute(future_date_query)
                future_sales = cursor.fetchall()
                for row in future_sales:
                    invalid_sales.append(dict(row))
                    logger.error(f"Found sale with future date: {dict(row)}")

                # Check orphaned items
                cursor = conn.execute(orphaned_items_query)
                orphaned = cursor.fetchall()
                for row in orphaned:
                    orphaned_items.append(dict(row))
                    logger.error(f"Found orphaned sale item: {dict(row)}")

            return invalid_sales, orphaned_items

        except sqlite3.Error as e:
            logger.error(f"Database error during diagnosis: {e}")
            raise DatabaseException(f"Database error during diagnosis: {e}")

    @staticmethod
    @db_operation(show_dialog=True)
    def fix_invalid_sales() -> None:
        """
        Fix invalid sales data by removing future sales and orphaned items.
        """
        logger.info("Starting sales data fix")

        try:
            invalid_sales, orphaned_items = DataValidationService.diagnose_sales_data()

            if not invalid_sales and not orphaned_items:
                logger.info("No invalid sales data found")
                return

            with DatabaseManager.get_db_connection() as conn:
                if invalid_sales:
                    # Validate and sanitize IDs first
                    sale_ids = []
                    for sale in invalid_sales:
                        try:
                            sale_id = int(sale.get('id', 0))
                            if 0 < sale_id <= 2147483647:
                                sale_ids.append(sale_id)
                        except (ValueError, TypeError):
                            logger.error(
                                f"Invalid sale ID skipped: {sale.get('id')}")
                            continue

                    if sale_ids:
                        # Use parameterized query with validated IDs
                        placeholders = ','.join(['?' for _ in sale_ids])
                        delete_items_query = f"""
                            DELETE FROM sale_items 
                            WHERE sale_id IN ({placeholders})
                        """
                        cursor = conn.execute(delete_items_query, sale_ids)

                if orphaned_items:
                    item_ids = [item['id'] for item in orphaned_items]
                    placeholders = ','.join('?' * len(item_ids))

                    logger.info(f"Deleting orphaned items: {item_ids}")
                    delete_orphaned_query = f"""
                        DELETE FROM sale_items 
                        WHERE id IN ({placeholders})
                    """
                    cursor = conn.execute(delete_orphaned_query, item_ids)
                    logger.info(f"Deleted {cursor.rowcount} orphaned items")

                conn.commit()
                logger.info("Sales data fix completed successfully")

        except sqlite3.Error as e:
            logger.error(f"Database error during fix: {e}")
            logger.error("Failed SQL operations details:")
            raise DatabaseException(f"Database error during fix: {e}")
        except Exception as e:
            logger.error(f"Error during sales fix: {e}")
            logger.error("Full error details:")
            raise

    @staticmethod
    def validate_all_data():
        """
        Validate all application data during startup.
        Add more validation methods here as needed.
        """
        try:
            # Validate sales data
            invalid_sales, orphaned_items = DataValidationService.diagnose_sales_data()

            if invalid_sales or orphaned_items:
                logger.warning(
                    f"Found {len(invalid_sales)} invalid sales and {len(orphaned_items)} orphaned items")
                try:
                    logger.info("Attempting to fix invalid data...")
                    DataValidationService.fix_invalid_sales()

                    # Verify the fix
                    remaining_invalid, remaining_orphaned = DataValidationService.diagnose_sales_data()
                    if remaining_invalid or remaining_orphaned:
                        logger.error("Failed to fix all invalid data!")
                        logger.error(
                            f"Remaining invalid sales: {len(remaining_invalid)}")
                        logger.error(
                            f"Remaining orphaned items: {len(remaining_orphaned)}")
                    else:
                        logger.info("Successfully fixed all invalid data")

                except Exception as fix_error:
                    logger.error(
                        f"Error while fixing invalid data: {str(fix_error)}")
                    # Log the specific items that failed to be fixed
                    logger.error(
                        f"Failed to fix invalid sales: {invalid_sales}")
                    logger.error(
                        f"Failed to fix orphaned items: {orphaned_items}")
            else:
                logger.info("All sales data is valid")

            # Add more validation checks here for other data types
            # Example:
            # DataValidationService.validate_inventory_data()
            # DataValidationService.validate_customer_data()

        except Exception as e:
            logger.error(f"Error during data validation: {e}")
            # Log full details of the error for debugging
            logger.error(
                f"Full validation error details: {str(e)}")
