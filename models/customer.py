from typing import Optional

class Customer:
    def __init__(self, id: int, identifier_9: str, identifier_4: Optional[str] = None):
        self.id = id
        self.identifier_9 = identifier_9
        self.identifier_4 = identifier_4

    @classmethod
    def from_row(cls, row: dict) -> 'Customer':
        return cls(
            id=row['id'],
            identifier_9=row['identifier_9'],
            identifier_4=row['identifier_4'] if 'identifier_4' in row else None
        )

    def __repr__(self) -> str:
        return f"Customer(id={self.id}, identifier_9='{self.identifier_9}', identifier_4='{self.identifier_4}')"
