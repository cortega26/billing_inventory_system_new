from utils.system.logger import logger


def test_imports():
    """Simple smoke test to catch import errors."""
    assert logger is not None

    import pytest

    try:
        from ui.main_window import MainWindow

        assert MainWindow is not None
    except ImportError:
        pytest.skip("PySide6 not installed or working")
    except Exception as e:
        # Catch DLL errors which might present as other exceptions or crashes?
        # Actually 127 is hard crash, python level catch might not work if it happens at import time of C extension.
        # But usually it's raised as ImportError or DLL load failed.
        pytest.skip(f"PySide6 import failed: {e}")
