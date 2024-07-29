from dataclasses import dataclass
from typing import Optional, List

@dataclass
class Customer:
    id: int
    identifier_9: str
    identifier_3or4: Optional[str] = None

    @classmethod
    def from_db_row(cls, row: dict) -> 'Customer':
        return cls(
            id=row['id'],
            identifier_9=row['identifier_9']
        )

    def update_identifier_9(self, new_identifier_9: str) -> None:
        if not isinstance(new_identifier_9, str) or len(new_identifier_9) != 9:
            raise ValueError("identifier_9 must be a string of 9 characters")
        self.identifier_9 = new_identifier_9

    def update_identifier_3or4(self, new_identifier_3or4: Optional[str]) -> None:
        if new_identifier_3or4 is not None:
            if not isinstance(new_identifier_3or4, str) or len(new_identifier_3or4) not in (3, 4):
                raise ValueError("identifier_3or4 must be a string of 3 or 4 characters")
        self.identifier_3or4 = new_identifier_3or4

    def get_all_identifiers(self) -> List[str]:
        return [self.identifier_9] + ([self.identifier_3or4] if self.identifier_3or4 else [])

    def __str__(self) -> str:
        identifiers = ', '.join(self.get_all_identifiers())
        return f"Customer(id={self.id}, identifiers=[{identifiers}])"