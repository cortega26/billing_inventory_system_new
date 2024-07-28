from database import execute_query, fetch_one, fetch_all
from models.sale import Sale, SaleItem
from services.inventory_service import InventoryService

class SaleService:
    @staticmethod
    def create_sale(customer_id, date, items):
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        query = 'INSERT INTO sales (customer_id, date, total_amount) VALUES (?, ?, ?)'
        cursor = execute_query(query, (customer_id, date, total_amount))
        sale_id = cursor.lastrowid
        
        for item in items:
            query = '''
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            execute_query(query, (sale_id, item['product_id'], item['quantity'], item['price']))
            
            InventoryService.update_quantity(item['product_id'], -item['quantity'])
        
        return sale_id

    @staticmethod
    def get_sale(sale_id):
        query = 'SELECT * FROM sales WHERE id = ?'
        row = fetch_one(query, (sale_id,))
        return Sale.from_row(row) if row else None

    @staticmethod
    def get_all_sales():
        query = 'SELECT * FROM sales'
        rows = fetch_all(query)
        return [Sale.from_row(row) for row in rows]

    @staticmethod
    def get_sale_items(sale_id):
        query = 'SELECT * FROM sale_items WHERE sale_id = ?'
        rows = fetch_all(query, (sale_id,))
        return [SaleItem.from_row(row) for row in rows]

    @staticmethod
    def delete_sale(sale_id):
        # Get sale items
        items = SaleService.get_sale_items(sale_id)
        
        # Update inventory
        for item in items:
            InventoryService.update_quantity(item.product_id, item.quantity)
        
        # Delete sale items
        execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))
        
        # Delete sale
        execute_query('DELETE FROM sales WHERE id = ?', (sale_id,))

    @staticmethod
    def get_total_sales(start_date, end_date):
        query = '''
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM sales
            WHERE date BETWEEN ? AND ?
        '''
        result = fetch_one(query, (start_date, end_date))
        return result['total'] if result else 0

    @staticmethod
    def get_sales_by_customer(customer_id):
        query = 'SELECT * FROM sales WHERE customer_id = ?'
        rows = fetch_all(query, (customer_id,))
        return [Sale.from_row(row) for row in rows]

    @staticmethod
    def get_top_selling_products(limit=10):
        query = '''
            SELECT p.id, p.name, SUM(si.quantity) as total_quantity, SUM(si.quantity * si.price) as total_revenue
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            GROUP BY p.id
            ORDER BY total_quantity DESC
            LIMIT ?
        '''
        rows = fetch_all(query, (limit,))
        return rows

    @staticmethod
    def get_daily_sales(start_date, end_date):
        query = '''
            SELECT date, SUM(total_amount) as daily_total
            FROM sales
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        '''
        rows = fetch_all(query, (start_date, end_date))
        return rows

    @staticmethod
    def update_sale(sale_id, updated_sale_data):
        # First, get the original sale
        original_sale = SaleService.get_sale(sale_id)
        if not original_sale:
            raise ValueError(f"Sale with id {sale_id} not found")

        # Update the sale record
        query = '''
            UPDATE sales 
            SET customer_id = ?, date = ?, total_amount = ?
            WHERE id = ?
        '''
        execute_query(query, (
            updated_sale_data['customer_id'],
            updated_sale_data['date'],
            sum(item['price'] * item['quantity'] for item in updated_sale_data['items']),
            sale_id
        ))

        # Get the original sale items
        original_items = SaleService.get_sale_items(sale_id)

        # Delete the original sale items
        execute_query('DELETE FROM sale_items WHERE sale_id = ?', (sale_id,))

        # Insert the updated sale items
        for item in updated_sale_data['items']:
            query = '''
                INSERT INTO sale_items (sale_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            '''
            execute_query(query, (sale_id, item['product_id'], item['quantity'], item['price']))

        # Update inventory
        inventory_service = InventoryService()
        for original_item in original_items:
            inventory_service.update_quantity(original_item.product_id, original_item.quantity)
        for new_item in updated_sale_data['items']:
            inventory_service.update_quantity(new_item['product_id'], -new_item['quantity'])