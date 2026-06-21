from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    """
    AuditLog entity with SQLModel implementation.
    """

    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    operation: str
    entity_type: str
    entity_id: Optional[int] = Field(default=None)
    actor: Optional[str] = Field(default=None)
    payload: Optional[str] = Field(default=None)
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
