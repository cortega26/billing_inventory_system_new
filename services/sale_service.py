from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from database import DatabaseManager
from models.sale import Sale, SaleItem
from services.inventory_service import InventoryService
from utils.logger import logger

class SaleService:
    @staticmethod
    def create_sale(customer_id: int, date: str, items: List[Dict[str, Any]]) -> Optional[int]:
        logger.debug(f"Creating sale for customer ID: {customer_id} on {date} with {len(items)} items")
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        query = 'INSERT INTO sales (customer_id, date, total_amount) VALUES (?, ?, ?)'
        cursor = DatabaseManager.execute_query(query, (customer_id, date, total_amount))
        sale_id = cursor.lastrowid
        
        if sale_id is None:
            logger.error("Failed to create sale record")
            return None

        for item in items:
            query = '''
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (sale_id, item['product_id'], item['quantity'], item['price']))
            
            InventoryService.update_quantity(item['product_id'], -item['quantity'])
        
        logger.info(f"Created sale with ID: {sale_id}")
        return sale_id

    @staticmethod
    def get_sale(sale_id: int) -> Optional[Sale]:
        logger.debug(f"Fetching sale with ID: {sale_id}")
        query = 'SELECT * FROM sales WHERE id = ?'
        row = DatabaseManager.fetch_one(query, (sale_id,))
        if row:
            sale = Sale.from_db_row(row)
            sale.items = SaleService.get_sale_items(sale_id)
            logger.debug(f"Retrieved sale: {sale}")
            return sale
        logger.debug(f"No sale found with ID: {sale_id}")
        return None

    @staticmethod
    def get_all_sales() -> List[Sale]:
        logger.debug("Fetching all sales")
        query = 'SELECT * FROM sales ORDER BY date DESC'
        rows = DatabaseManager.fetch_all(query)
        sales = [Sale.from_db_row(row) for row in rows]
        for sale in sales:
            sale.items = SaleService.get_sale_items(sale.id)
        logger.debug(f"Retrieved {len(sales)} sales")
        return sales

    @staticmethod
    def get_sale_items(sale_id: int) -> List[SaleItem]:
        logger.debug(f"Fetching items for sale ID: {sale_id}")
        query = 'SELECT * FROM sale_items WHERE sale_id = ?'
        rows = DatabaseManager.fetch_all(query, (sale_id,))
        items = [SaleItem.from_db_row(row) for row in rows]
        logger.debug(f"Retrieved {len(items)} items for sale ID: {sale_id}")
        return items

    @staticmethod
    def delete_sale(sale_id: int) -> None:
        logger.debug(f"Deleting sale with ID: {sale_id}")
        items = SaleService.get_sale_items(sale_id)
        
        for item in items:
            InventoryService.update_quantity(item.product_id, item.quantity)
        
        DatabaseManager.execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))
        DatabaseManager.execute_query('DELETE FROM sales WHERE id = ?', (sale_id,))
        logger.info(f"Deleted sale with ID: {sale_id}")

    @staticmethod
    def get_total_sales(start_date: str, end_date: str) -> float:
        logger.debug(f"Calculating total sales from {start_date} to {end_date}")
        query = '''
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ?
        '''
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        total = float(result['total']) if result else 0
        logger.debug(f"Total sales: {total}")
        return total

    @staticmethod
    def get_sales_by_customer(customer_id: int) -> List[Sale]:
        logger.debug(f"Fetching sales for customer ID: {customer_id}")
        query = 'SELECT * FROM sales WHERE customer_id = ? ORDER BY date DESC'
        rows = DatabaseManager.fetch_all(query, (customer_id,))
        sales = [Sale.from_db_row(row) for row in rows]
        for sale in sales:
            sale.items = SaleService.get_sale_items(sale.id)
        logger.debug(f"Retrieved {len(sales)} sales for customer ID: {customer_id}")
        return sales

    @staticmethod
    def get_top_selling_products(limit: int = 10) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching top {limit} selling products")
        query = '''
            SELECT p.id, p.name, SUM(si.quantity) as total_quantity, SUM(si.quantity * si.price) as total_revenue
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            GROUP BY p.id
            ORDER BY total_quantity DESC
            LIMIT ?
        '''
        return DatabaseManager.fetch_all(query, (limit,))

    @staticmethod
    def get_daily_sales(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching daily sales from {start_date} to {end_date}")
        query = '''
            SELECT date, SUM(total_amount) as daily_total
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        '''
        return DatabaseManager.fetch_all(query, (start_date, end_date))

    @staticmethod
    def update_sale(sale_id: int, customer_id: int, date: str, items: List[Dict[str, Any]]) -> None:
        logger.debug(f"Updating sale with ID: {sale_id}")
        old_items = SaleService.get_sale_items(sale_id)
        
        # Revert inventory changes from old items
        for item in old_items:
            InventoryService.update_quantity(item.product_id, item.quantity)
        
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        query = 'UPDATE sales SET customer_id = ?, date = ?, total_amount = ? WHERE id = ?'
        DatabaseManager.execute_query(query, (customer_id, date, total_amount, sale_id))
        
        # Delete old items
        DatabaseManager.execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))
        
        # Insert new items and update inventory
        for item in items:
            query = '''
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            DatabaseManager.execute_query(query, (sale_id, item['product_id'], item['quantity'], item['price']))
            InventoryService.update_quantity(item['product_id'], -item['quantity'])
        
        logger.info(f"Updated sale with ID: {sale_id}")

    @staticmethod
    def get_sales_stats(start_date: str, end_date: str) -> Dict[str, Any]:
        logger.debug(f"Fetching sales stats from {start_date} to {end_date}")
        query = '''
        SELECT 
            COUNT(DISTINCT s.id) as total_sales,
            SUM(s.total_amount) as total_revenue,
            AVG(s.total_amount) as average_sale_amount,
            COUNT(DISTINCT s.customer_id) as unique_customers
        FROM sales s
        WHERE s.date BETWEEN ? AND ?
        '''
        result = DatabaseManager.fetch_one(query, (start_date, end_date))
        stats = {
            'total_sales': result['total_sales'] if result else 0,
            'total_revenue': float(result['total_revenue']) if result and result['total_revenue'] else 0.0,
            'average_sale_amount': float(result['average_sale_amount']) if result and result['average_sale_amount'] else 0.0,
            'unique_customers': result['unique_customers'] if result else 0
        }
        logger.debug(f"Sales stats: {stats}")
        return stats