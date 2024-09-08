from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from utils.exceptions import ValidationException

@dataclass
class Customer:
    id: int
    identifier_9: str
    identifier_3or4: Optional[str] = None
    _identifiers: List[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.validate_identifier_9(self.identifier_9)
        if self.identifier_3or4:
            self.validate_identifier_3or4(self.identifier_3or4)
        self._identifiers = [self.identifier_9]
        if self.identifier_3or4:
            self._identifiers.append(self.identifier_3or4)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Customer":
        return cls(
            id=row["id"],
            identifier_9=row["identifier_9"],
            identifier_3or4=row.get("identifier_3or4"),
        )

    @staticmethod
    def validate_identifier_9(identifier: str) -> None:
        if not isinstance(identifier, str) or len(identifier) != 9 or not identifier.isdigit():
            raise ValidationException("identifier_9 must be a string of 9 digits")

    @staticmethod
    def validate_identifier_3or4(identifier: Optional[str]) -> None:
        if identifier is not None:
            if not isinstance(identifier, str) or len(identifier) not in (3, 4) or not identifier.isdigit():
                raise ValidationException("identifier_3or4 must be a string of 3 or 4 digits")

    def update_identifier_9(self, new_identifier_9: str) -> None:
        self.validate_identifier_9(new_identifier_9)
        self.identifier_9 = new_identifier_9
        self._identifiers[0] = new_identifier_9

    def update_identifier_3or4(self, new_identifier_3or4: Optional[str]) -> None:
        self.validate_identifier_3or4(new_identifier_3or4)
        self.identifier_3or4 = new_identifier_3or4
        if new_identifier_3or4:
            if len(self._identifiers) > 1:
                self._identifiers[1] = new_identifier_3or4
            else:
                self._identifiers.append(new_identifier_3or4)
        elif len(self._identifiers) > 1:
            self._identifiers.pop()

    def get_all_identifiers(self) -> List[str]:
        return self._identifiers.copy()

    def __str__(self) -> str:
        identifiers = ", ".join(self._identifiers)
        return f"Customer(id={self.id}, identifiers=[{identifiers}])"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Customer):
            return NotImplemented
        return self.id == other.id and self._identifiers == other._identifiers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "identifier_9": self.identifier_9,
            "identifier_3or4": self.identifier_3or4,
        }
