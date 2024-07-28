from typing import Optional, Union, List
from sqlite3 import Row

class CustomerIdentifier:
    def __init__(self, id: int, customer_id: int, identifier_3or4: str):
        self.id = id
        self.customer_id = customer_id
        self.identifier_3or4 = identifier_3or4

    def __repr__(self) -> str:
        return f"CustomerIdentifier(id={self.id}, customer_id={self.customer_id}, identifier_3or4='{self.identifier_3or4}')"

class Customer:
    def __init__(self, id: int, identifier_9: str, identifiers_3or4: Optional[List[CustomerIdentifier]] = None):
        self.id = id
        self.identifier_9 = identifier_9
        self.identifiers_3or4 = identifiers_3or4 or []

    @classmethod
    def from_row(cls, row: Union[Row, dict]) -> 'Customer':
        if isinstance(row, Row):
            return cls(
                id=row['id'],
                identifier_9=row['identifier_9']
            )
        elif isinstance(row, dict):
            return cls(
                id=row['id'],
                identifier_9=row['identifier_9']
            )
        else:
            raise TypeError("row must be either sqlite3.Row or dict")

    def __repr__(self) -> str:
        return f"Customer(id={self.id}, identifier_9='{self.identifier_9}', identifiers_3or4={self.identifiers_3or4})"