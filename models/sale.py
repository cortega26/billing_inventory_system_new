from typing import Dict, Any

class Sale:
    def __init__(self, id: int, customer_id: int, date: str, total_amount: int):
        self.id = id
        self.customer_id = customer_id
        self.date = date
        self.total_amount = total_amount

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Sale':
        return cls(
            id=row['id'],
            customer_id=row['customer_id'],
            date=row['date'],
            total_amount=row['total_amount']
        )

    def __repr__(self) -> str:
        return f"Sale(id={self.id}, customer_id={self.customer_id}, date='{self.date}', total_amount={self.total_amount})"

class SaleItem:
    def __init__(self, id: int, sale_id: int, product_id: int, quantity: int, price: int):
        self.id = id
        self.sale_id = sale_id
        self.product_id = product_id
        self.quantity = quantity
        self.price = price

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'SaleItem':
        return cls(
            id=row['id'],
            sale_id=row['sale_id'],
            product_id=row['product_id'],
            quantity=row['quantity'],
            price=row['price']
        )

    def __repr__(self) -> str:
        return f"SaleItem(id={self.id}, sale_id={self.sale_id}, product_id={self.product_id}, quantity={self.quantity}, price={self.price})"
