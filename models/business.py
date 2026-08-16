"""Business value type (no DB table) and business id validation constant."""

import re
from dataclasses import dataclass

BUSINESS_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class Business:
    """Plain value type describing a configured business (no DB table)."""

    id: str
    name: str
    db_filename: str

    @classmethod
    def from_dict(cls, data: dict) -> "Business":
        return cls(id=data["id"], name=data["name"], db_filename=data["db_filename"])

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "db_filename": self.db_filename}
