import uuid

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QLabel
from sqlmodel import SQLModel, create_engine

from config import config
from ui.dashboard_view import DashboardView

# DashboardView builds charts through the analytics engine, which opens a
# read-only connection to the active business's database FILE (not the
# in-memory DatabaseManager). get_safe_db_path() always resolves db_filename
# relative to the repo root, so per-test isolation has to come from a unique
# filename rather than a tmp_path redirect. Seed that file with the full
# schema so chart queries succeed; the profile assertions never depend on
# query results.


@pytest.fixture
def set_dashboard_profile(db_manager):
    created_paths: list = []

    def _set(profile):
        db_filename = f"dashboard_{profile}_test_{uuid.uuid4().hex}.db"
        config.set(
            "businesses",
            [
                {
                    "id": "default",
                    "name": "Principal",
                    "db_filename": db_filename,
                    "dashboard": profile,
                }
            ],
        )
        config.set("active_business", "default")
        db_path = config.get_active_database_path()
        engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(engine)
        engine.dispose()
        created_paths.append(db_path)

    yield _set

    for path in created_paths:
        path.unlink(missing_ok=True)


def _metric_labels(view: DashboardView) -> list[str]:
    return [label.text() for label in view.findChildren(QLabel)]


def test_reseller_profile_shows_inventory_value_card(qtbot, set_dashboard_profile):
    set_dashboard_profile("reseller")
    view = DashboardView()
    qtbot.addWidget(view)

    labels = _metric_labels(view)
    assert "Valor Inventario" in labels
    assert "Unidades Vendidas" not in labels


def test_production_profile_shows_units_card(qtbot, set_dashboard_profile):
    set_dashboard_profile("production")
    view = DashboardView()
    qtbot.addWidget(view)

    labels = _metric_labels(view)
    assert "Unidades Vendidas" in labels
    assert "Valor Inventario" not in labels


def test_unknown_profile_raises_value_error(qtbot, monkeypatch):
    def fake_get_active_business():
        return {"id": "default", "name": "Principal", "dashboard": "bogus"}

    monkeypatch.setattr(config, "get_active_business", fake_get_active_business)
    with pytest.raises(ValueError, match="Unknown dashboard profile"):
        DashboardView()
