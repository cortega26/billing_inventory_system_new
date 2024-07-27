class Sale:
    def __init__(self, id, customer_id, date, total_amount):
        self.id = id
        self.customer_id = customer_id
        self.date = date
        self.total_amount = total_amount

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            customer_id=row['customer_id'],
            date=row['date'],
            total_amount=row['total_amount']
        )

class SaleItem:
    def __init__(self, id, sale_id, product_id, quantity, price):
        self.id = id
        self.sale_id = sale_id
        self.product_id = product_id
        self.quantity = quantity
        self.price = price

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            sale_id=row['sale_id'],
            product_id=row['product_id'],
            quantity=row['quantity'],
            price=row['price']
        )