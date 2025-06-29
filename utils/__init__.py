"""Utility package providing optional helpers and common functionality.

The submodules in this package are mostly related to the Qt based UI.  Importing
them unconditionally makes the package unusable in environments where the
``PySide6`` dependency is not installed (for example, in the unit test
environment).  To keep import side effects to a minimum we expose the
submodules lazily and avoid importing them on package initialisation.
"""

from importlib import import_module
from types import ModuleType
from typing import Any

__all__ = [
    "helpers",
    "decorators",
    "exceptions",
    "data_handling",
    "ui",
    "system",
    "validation",
]


def __getattr__(name: str) -> ModuleType | Any:  # pragma: no cover - passthrough
    """Dynamically import submodules on first access."""
    if name in __all__:
        return import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
