class Inventory:
    def __init__(self, id, product_id, quantity):
        self.id = id
        self.product_id = product_id
        self.quantity = quantity

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            product_id=row['product_id'],
            quantity=row['quantity']
        )