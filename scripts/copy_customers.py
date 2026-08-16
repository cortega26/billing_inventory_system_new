"""Copy customers (identity only) from one business database to another.

One-time seed for the per-business database design: copies El Rincón de
Ébano's customers into CasaBea without touching financial state. Idempotent:
identifier_9 values already present in the target are never overwritten, so
re-running the script doubles as a one-way refresh. Financial columns
(current_balance, credit_limit) are never read or written: debts belong to
the source business, not the target.

The target database must already exist and be migrated (run init_db() on it
once, e.g. by opening the business in the app or
`python -c "from database import init_db; init_db('<target>')"`).

Usage:
    python scripts/copy_customers.py [--source PATH] [--target PATH]
        [--include-inactive] [--dry-run]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import ConfigValidationError, config  # noqa: E402
from utils.exceptions import ValidationException  # noqa: E402
from utils.validation.validators import (  # noqa: E402
    validate_3or4digit_identifier,
    validate_9digit_identifier,
)

REQUIRED_TABLES = ("customers", "customer_identifiers")


def copy_customers(
    source_path: Path,
    target_path: Path,
    include_inactive: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """Copy customers (identity only) from source DB to target DB.

    Idempotent: existing identifier_9 values in the target are never
    overwritten. Financial state is never copied. Invalid identifier rows are
    counted and skipped, never fatal. Returns a summary dict
    {"inserted": int, "existing": int, "invalid": int}.
    """
    if not source_path.exists():
        raise RuntimeError(f"No existe la base de datos de origen: {source_path}")
    if not target_path.exists():
        raise RuntimeError(f"No existe la base de datos de destino: {target_path}")

    source_conn = sqlite3.connect(str(source_path))
    source_conn.row_factory = sqlite3.Row
    try:
        try:
            active_filter = "" if include_inactive else "WHERE c.is_active = 1"
            source_customers = source_conn.execute(
                "SELECT c.identifier_9, c.name, c.is_active, ci.identifier_3or4 "
                "FROM customers c "
                "LEFT JOIN customer_identifiers ci ON ci.customer_id = c.id "
                f"{active_filter} "
                "ORDER BY c.id"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise RuntimeError(
                f"No se pudo leer la base de datos de origen: {exc}"
            ) from exc
    finally:
        source_conn.close()

    target_conn = sqlite3.connect(str(target_path), isolation_level=None)
    try:
        try:
            tables = {
                row[0]
                for row in target_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        except sqlite3.DatabaseError as exc:
            raise RuntimeError(
                f"No se pudo leer la base de datos de destino: {exc}"
            ) from exc
        missing_tables = [name for name in REQUIRED_TABLES if name not in tables]
        if missing_tables:
            raise RuntimeError(
                "La base de datos de destino no tiene las tablas requeridas: "
                f"{', '.join(missing_tables)}. Ejecute init_db() sobre el "
                "destino antes de copiar clientes."
            )

        existing_identifiers = {
            row[0] for row in target_conn.execute("SELECT identifier_9 FROM customers")
        }

        if not dry_run:
            target_conn.execute("BEGIN")

        summary = {"inserted": 0, "existing": 0, "invalid": 0}
        try:
            for row in source_customers:
                identifier_9 = row["identifier_9"]
                if identifier_9 in existing_identifiers:
                    summary["existing"] += 1
                    continue

                identifier_3or4 = row["identifier_3or4"]
                has_identifier_3or4 = (
                    identifier_3or4 is not None and identifier_3or4 != ""
                )
                try:
                    validate_9digit_identifier(identifier_9)
                    if has_identifier_3or4:
                        validate_3or4digit_identifier(identifier_3or4)
                except ValidationException as exc:
                    summary["invalid"] += 1
                    print(
                        f"Advertencia: se omite cliente {identifier_9!r}: {exc}",
                        file=sys.stderr,
                    )
                    continue

                if not dry_run:
                    cursor = target_conn.execute(
                        "INSERT INTO customers (identifier_9, name, is_active) "
                        "VALUES (?, ?, ?)",
                        (identifier_9, row["name"], row["is_active"]),
                    )
                    if has_identifier_3or4:
                        target_conn.execute(
                            "INSERT INTO customer_identifiers "
                            "(customer_id, identifier_3or4) VALUES (?, ?)",
                            (cursor.lastrowid, identifier_3or4),
                        )
                summary["inserted"] += 1

            if not dry_run:
                target_conn.execute("COMMIT")
        except Exception:
            if not dry_run:
                target_conn.execute("ROLLBACK")
            raise
    finally:
        target_conn.close()

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copia clientes (solo identidad) de una base de datos de "
        "negocio a otra, sin sobrescribir los existentes."
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Base de datos de origen (por defecto: negocio 'default').",
    )
    parser.add_argument(
        "--target",
        type=Path,
        help="Base de datos de destino (por defecto: negocio 'casabea').",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Incluir clientes archivados (is_active = 0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo informar la operación sin escribir datos.",
    )
    args = parser.parse_args(argv)

    if args.source is None or args.target is None:
        try:
            if args.source is None:
                args.source = config.get_business_db_path("default")
            if args.target is None:
                args.target = config.get_business_db_path("casabea")
        except ConfigValidationError as exc:
            parser.error(f"No se pudo resolver el negocio por defecto: {exc}")

    try:
        summary = copy_customers(
            args.source,
            args.target,
            include_inactive=args.include_inactive,
            dry_run=args.dry_run,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    message = (
        f"Clientes: {summary['inserted']} insertados, "
        f"{summary['existing']} ya existentes, "
        f"{summary['invalid']} omitidos por datos inválidos."
    )
    if args.dry_run:
        message += " (modo simulación: no se escribió nada)"
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
