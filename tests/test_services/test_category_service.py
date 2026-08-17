from types import SimpleNamespace

import pytest

from database.database_manager import DatabaseManager
from services.category_service import CategoryService
from utils.exceptions import DatabaseException


@pytest.fixture
def category_service(db_manager):
    return CategoryService()


def test_create_category_returns_int_id(category_service):
    category_id = category_service.create_category("Test Cat")

    assert isinstance(category_id, int)
    assert category_service.get_category(category_id) is not None


def test_get_category_missing_returns_none(category_service):
    assert category_service.get_category(999999) is None


def test_get_category_by_name_missing_returns_none(category_service):
    assert category_service.get_category_by_name("Categoría Inexistente") is None


def test_get_category_returns_matching_category(category_service):
    category_id = category_service.create_category("Test Cat")

    category = category_service.get_category(category_id)

    assert category is not None
    assert category.name == "Test Cat"


def test_get_category_by_name_returns_matching_category(category_service):
    category_service.create_category("Test Cat")

    category = category_service.get_category_by_name("Test Cat")

    assert category is not None
    assert category.name == "Test Cat"


def test_create_category_raises_database_exception_when_lastrowid_missing(
    category_service, mocker
):
    mocker.patch.object(
        DatabaseManager,
        "execute_query",
        return_value=SimpleNamespace(lastrowid=None),
    )

    with pytest.raises(DatabaseException):
        category_service.create_category("Test Cat")
