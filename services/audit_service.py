import json
from typing import Any

from database.database_manager import DatabaseManager
from utils.exceptions import ValidationException


class AuditService:
    @staticmethod
    def log_operation(
        operation: str,
        entity_type: str,
        entity_id: int | None,
        payload: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> None:
        if not operation:
            raise ValidationException("operation is required for audit log")
        if not entity_type:
            raise ValidationException("entity_type is required for audit log")

        serialized_payload = None
        if payload is not None:
            serialized_payload = json.dumps(
                payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            )

        DatabaseManager.execute_query(
            """
            INSERT INTO audit_log (operation, entity_type, entity_id, actor, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (operation, entity_type, entity_id, actor, serialized_payload),
        )

    @staticmethod
    def get_entries(
        entity_type: str | None = None,
        entity_id: int | None = None,
        operation: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params = []

        if entity_type is not None:
            filters.append("entity_type = ?")
            params.append(entity_type)
        if entity_id is not None:
            filters.append("entity_id = ?")
            params.append(entity_id)
        if operation is not None:
            filters.append("operation = ?")
            params.append(operation)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"""
            SELECT *
            FROM audit_log
            {where_clause}
            ORDER BY id
        """  # nosec B608
        return DatabaseManager.fetch_all(query, tuple(params))

    @staticmethod
    def search_entries(
        entity_type: str | None = None,
        operation: str | None = None,
        actor: str | None = None,
        search_term: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        filters = []
        params = []

        if entity_type:
            filters.append("entity_type = ?")
            params.append(entity_type)

        if operation:
            filters.append("operation = ?")
            params.append(operation)

        if actor:
            filters.append("LOWER(COALESCE(actor, '')) LIKE LOWER(?)")
            params.append(f"%{actor.strip()}%")

        if start_date:
            filters.append("DATE(timestamp) >= DATE(?)")
            params.append(start_date)

        if end_date:
            filters.append("DATE(timestamp) <= DATE(?)")
            params.append(end_date)

        if search_term:
            search_pattern = f"%{search_term.strip()}%"
            filters.append(
                "("
                "LOWER(operation) LIKE LOWER(?) OR "
                "LOWER(entity_type) LIKE LOWER(?) OR "
                "CAST(COALESCE(entity_id, '') AS TEXT) LIKE ? OR "
                "LOWER(COALESCE(actor, '')) LIKE LOWER(?) OR "
                "LOWER(COALESCE(payload, '')) LIKE LOWER(?)"
                ")"
            )
            params.extend([search_pattern] * 5)

        normalized_limit = max(1, min(int(limit), 1000))
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"""
            SELECT *
            FROM audit_log
            {where_clause}
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """  # nosec B608
        params.append(normalized_limit)

        return DatabaseManager.fetch_all(query, tuple(params))
