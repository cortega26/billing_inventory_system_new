from typing import Dict, Optional, Any

class Product:
    def __init__(self, id: int, name: str, description: Optional[str] = None):
        self.id = id
        self.name = name
        self.description = description

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Product':
        return cls(
            id=row['id'],
            name=row['name'],
            description=row['description'] if 'description' in row else None
        )

    def __repr__(self) -> str:
        return f"Product(id={self.id}, name='{self.name}', description='{self.description}')"

    def update(self, name: Optional[str] = None, description: Optional[str] = None) -> None:
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
