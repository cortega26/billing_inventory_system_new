from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    """
    AuditLog entity with SQLModel implementation.
    """

    __tablename__: str = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    operation: str
    entity_type: str
    entity_id: int | None = Field(default=None)
    actor: str | None = Field(default=None)
    payload: str | None = Field(default=None)
    timestamp: datetime | None = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
