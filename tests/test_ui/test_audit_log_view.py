from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from services.audit_service import AuditService
from ui.audit_log_view import AuditLogView


def test_audit_log_view_displays_entries_and_payload(qtbot, db_manager):
    AuditService.log_operation(
        "create_customer",
        "customer",
        7,
        {"identifier_9": "923456789", "has_name": True},
        actor="caja-01",
    )

    view = AuditLogView()
    qtbot.addWidget(view)

    assert view.audit_table.rowCount() == 1
    assert view.audit_table.item(0, 2).text() == "create_customer"
    assert view.audit_table.item(0, 3).text() == "customer"
    assert view.audit_table.item(0, 5).text() == "caja-01"
    assert '"identifier_9": "923456789"' in view.detail_text.toPlainText()


def test_audit_log_view_exports_visible_entries(qtbot, db_manager, tmp_path, monkeypatch):
    AuditService.log_operation(
        "delete_product",
        "product",
        11,
        {"mode": "archive"},
    )

    exported_file = tmp_path / "audit_log.csv"
    monkeypatch.setattr(
        "ui.audit_log_view.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(exported_file), "CSV Files (*.csv)"),
    )
    monkeypatch.setattr(
        "ui.audit_log_view.show_info_message",
        lambda *args, **kwargs: None,
    )

    view = AuditLogView()
    qtbot.addWidget(view)
    view.export_current_view()

    content = Path(exported_file).read_text(encoding="utf-8")
    assert "operation,entity_type,entity_id" in content
    assert "delete_product,product,11" in content