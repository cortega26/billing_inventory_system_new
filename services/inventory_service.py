from database import execute_query, fetch_one, fetch_all
from models.inventory import Inventory

class InventoryService:
    @staticmethod
    def update_quantity(product_id, quantity_change):
        # Check if inventory record exists
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        inventory = fetch_one(query, (product_id,))
        
        if inventory:
            # Update existing inventory
            new_quantity = inventory['quantity'] + quantity_change
            query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
            execute_query(query, (new_quantity, product_id))
        else:
            # Create new inventory record
            query = 'INSERT INTO inventory (product_id, quantity) VALUES (?, ?)'
            execute_query(query, (product_id, quantity_change))

    @staticmethod
    def get_inventory(product_id):
        query = 'SELECT * FROM inventory WHERE product_id = ?'
        row = fetch_one(query, (product_id,))
        return Inventory.from_row(row) if row else None

    @staticmethod
    def get_all_inventory():
        query = '''
            SELECT p.id as product_id, p.name as product_name, COALESCE(i.quantity, 0) as quantity
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id
        '''
        rows = fetch_all(query)
        return rows

    @staticmethod
    def set_quantity(product_id, quantity):
        query = 'UPDATE inventory SET quantity = ? WHERE product_id = ?'
        execute_query(query, (quantity, product_id))

    @staticmethod
    def delete_inventory(product_id):
        query = 'DELETE FROM inventory WHERE product_id = ?'
        execute_query(query, (product_id,))