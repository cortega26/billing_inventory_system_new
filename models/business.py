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

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "db_filename": self.db_filename}
