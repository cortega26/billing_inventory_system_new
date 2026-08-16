"""Tests for scripts/copy_customers.py.

The test databases use the repo's canonical customers/customer_identifiers
DDL (see schema.sql). The live El Rincón database has extra financial columns
(current_balance, credit_limit) that the copy must never read or write.
"""

import sqlite3

from scripts.copy_customers import copy_customers

CUSTOMERS_DDL = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE,
    name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    deleted_at TEXT
)
"""

IDENTIFIERS_DDL = """
CREATE TABLE customer_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    identifier_3or4 TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
)
"""


def make_database(path):
    conn = sqlite3.connect(str(path))
    conn.executescript(f"{CUSTOMERS_DDL}; {IDENTIFIERS_DDL}")
    conn.close()


def add_customer(conn, identifier_9, name=None, is_active=1, identifier_3or4=None):
    cursor = conn.execute(
        "INSERT INTO customers (identifier_9, name, is_active) VALUES (?, ?, ?)",
        (identifier_9, name, is_active),
    )
    if identifier_3or4 is not None:
        conn.execute(
            "INSERT INTO customer_identifiers (customer_id, identifier_3or4) "
            "VALUES (?, ?)",
            (cursor.lastrowid, identifier_3or4),
        )
    conn.commit()


def read_target(path):
    conn = sqlite3.connect(str(path))
    customers = conn.execute(
        "SELECT id, identifier_9, name, is_active FROM customers ORDER BY id"
    ).fetchall()
    identifiers = conn.execute(
        "SELECT customer_id, identifier_3or4 FROM customer_identifiers "
        "ORDER BY customer_id"
    ).fetchall()
    conn.close()
    return customers, identifiers


def test_copies_active_customers_with_department_ids(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    make_database(source_path)
    make_database(target_path)

    source = sqlite3.connect(str(source_path))
    add_customer(source, "912345678", name="Ana Pérez", identifier_3or4="101")
    add_customer(source, "987654321", name="Luis Soto")
    source.close()

    summary = copy_customers(source_path, target_path)

    assert summary == {"inserted": 2, "existing": 0, "invalid": 0}
    customers, identifiers = read_target(target_path)
    assert customers == [
        (1, "912345678", "Ana Pérez", 1),
        (2, "987654321", "Luis Soto", 1),
    ]
    assert identifiers == [(1, "101")]


def test_is_idempotent_and_never_overwrites(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    make_database(source_path)
    make_database(target_path)

    source = sqlite3.connect(str(source_path))
    add_customer(source, "912345678", name="Nombre original")
    source.close()

    target = sqlite3.connect(str(target_path))
    target.execute(
        "INSERT INTO customers (identifier_9, name, is_active) VALUES (?, ?, 1)",
        ("912345678", "Nombre modificado"),
    )
    target.commit()
    target.close()

    assert copy_customers(source_path, target_path) == {
        "inserted": 0,
        "existing": 1,
        "invalid": 0,
    }

    source = sqlite3.connect(str(source_path))
    source.execute(
        "UPDATE customers SET name = ? WHERE identifier_9 = ?",
        ("Nombre fuente actualizado", "912345678"),
    )
    source.commit()
    source.close()

    assert copy_customers(source_path, target_path) == {
        "inserted": 0,
        "existing": 1,
        "invalid": 0,
    }
    customers, _ = read_target(target_path)
    assert customers == [(1, "912345678", "Nombre modificado", 1)]


def test_skips_inactive_by_default_and_includes_with_flag(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    make_database(source_path)
    make_database(target_path)

    source = sqlite3.connect(str(source_path))
    add_customer(source, "912345678", name="Activa")
    add_customer(source, "987654321", name="Archivada", is_active=0)
    source.close()

    assert copy_customers(source_path, target_path) == {
        "inserted": 1,
        "existing": 0,
        "invalid": 0,
    }
    customers, _ = read_target(target_path)
    assert [c[1] for c in customers] == ["912345678"]

    assert copy_customers(source_path, target_path, include_inactive=True) == {
        "inserted": 1,
        "existing": 1,
        "invalid": 0,
    }
    customers, _ = read_target(target_path)
    assert [c[1] for c in customers] == ["912345678", "987654321"]


def test_invalid_identifier_is_counted_not_aborted(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    make_database(source_path)
    make_database(target_path)

    source = sqlite3.connect(str(source_path))
    add_customer(source, "112345678", name="Inválido")
    add_customer(source, "912345678", name="Válido")
    source.close()

    summary = copy_customers(source_path, target_path)

    assert summary == {"inserted": 1, "existing": 0, "invalid": 1}
    customers, _ = read_target(target_path)
    assert [c[1] for c in customers] == ["912345678"]


def test_dry_run_writes_nothing(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    make_database(source_path)
    make_database(target_path)

    source = sqlite3.connect(str(source_path))
    add_customer(source, "912345678", name="Ana", identifier_3or4="101")
    add_customer(source, "987654321", name="Luis")
    source.close()

    summary = copy_customers(source_path, target_path, dry_run=True)

    assert summary == {"inserted": 2, "existing": 0, "invalid": 0}
    customers, identifiers = read_target(target_path)
    assert customers == []
    assert identifiers == []


def test_skips_identifier_row_when_3or4_missing(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    make_database(source_path)
    make_database(target_path)

    source = sqlite3.connect(str(source_path))
    add_customer(source, "912345678", name="Con departamento", identifier_3or4="101")
    add_customer(source, "987654321", name="Sin departamento")
    add_customer(source, "955667788", name="Departamento vacío", identifier_3or4="")
    source.close()

    summary = copy_customers(source_path, target_path)

    assert summary == {"inserted": 3, "existing": 0, "invalid": 0}
    customers, identifiers = read_target(target_path)
    assert len(customers) == 3
    assert identifiers == [(1, "101")]
