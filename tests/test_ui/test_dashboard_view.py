import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QLabel
from sqlmodel import SQLModel, create_engine

from config import config
from ui.dashboard_view import DashboardView

# DashboardView builds charts through the analytics engine, which opens a
# read-only connection to the active business's database FILE (not the
# in-memory DatabaseManager). Seed that file with the full schema so chart
# queries succeed; the profile assertions never depend on query results.
RESELLER_DB = "dashboard_reseller_test.db"
PRODUCTION_DB = "dashboard_production_test.db"


@pytest.fixture
def set_dashboard_profile(db_manager):
    def _set(profile):
        db_filename = (
            RESELLER_DB if profile == "reseller" else PRODUCTION_DB
        )
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
        if not db_path.exists():
            engine = create_engine(f"sqlite:///{db_path}")
            SQLModel.metadata.create_all(engine)

    return _set


def _metric_labels(view: DashboardView) -> list[str]:
    return [label.text() for label in view.findChildren(QLabel)]


def test_reseller_profile_shows_inventory_value_card(
    qtbot, set_dashboard_profile
):
    set_dashboard_profile("reseller")
    view = DashboardView()
    qtbot.addWidget(view)

    labels = _metric_labels(view)
    assert "Valor Inventario" in labels
    assert "Unidades Vendidas" not in labels


def test_production_profile_shows_units_card(
    qtbot, set_dashboard_profile
):
    set_dashboard_profile("production")
    view = DashboardView()
    qtbot.addWidget(view)

    labels = _metric_labels(view)
    assert "Unidades Vendidas" in labels
    assert "Valor Inventario" not in labels
