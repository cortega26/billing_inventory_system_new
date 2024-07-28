from typing import Dict, Any

class Purchase:
    def __init__(self, id: int, supplier: str, date: str, total_amount: float):
        self.id = id
        self.supplier = supplier
        self.date = date
        self.total_amount = total_amount

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Purchase':
        return cls(
            id=int(row['id']),
            supplier=row['supplier'],
            date=row['date'],
            total_amount=float(row['total_amount'])
        )

    def __repr__(self) -> str:
        return f"Purchase(id={self.id}, supplier='{self.supplier}', date='{self.date}', total_amount={self.total_amount})"

class PurchaseItem:
    def __init__(self, id: int, purchase_id: int, product_id: int, quantity: int, price: float):
        self.id = id
        self.purchase_id = purchase_id
        self.product_id = product_id
        self.quantity = quantity
        self.price = price

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'PurchaseItem':
        return cls(
            id=int(row['id']),
            purchase_id=int(row['purchase_id']),
            product_id=int(row['product_id']),
            quantity=int(row['quantity']),
            price=float(row['price'])
        )

    def __repr__(self) -> str:
        return f"PurchaseItem(id={self.id}, purchase_id={self.purchase_id}, product_id={self.product_id}, quantity={self.quantity}, price={self.price})"