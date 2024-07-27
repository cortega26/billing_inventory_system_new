class Purchase:
    def __init__(self, id, supplier, date, total_amount):
        self.id = id
        self.supplier = supplier
        self.date = date
        self.total_amount = total_amount

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            supplier=row['supplier'],
            date=row['date'],
            total_amount=row['total_amount']
        )

class PurchaseItem:
    def __init__(self, id, purchase_id, product_id, quantity, price):
        self.id = id
        self.purchase_id = purchase_id
        self.product_id = product_id
        self.quantity = quantity
        self.price = price

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            purchase_id=row['purchase_id'],
            product_id=row['product_id'],
            quantity=row['quantity'],
            price=row['price']
        )