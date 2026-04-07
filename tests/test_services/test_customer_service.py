import pytest

from database.database_manager import DatabaseManager
from services.audit_service import AuditService
from services.customer_service import CustomerService
from utils.exceptions import DatabaseException, NotFoundException, ValidationException
from utils.system.event_system import event_system


def capture_signal(signal):
    payloads = []

    def handler(payload=None):
        payloads.append(payload)

    signal.connect(handler)
    return payloads, handler


@pytest.fixture
def customer_service(db_manager):
    return CustomerService()


@pytest.fixture
def sample_customer_data():
    return {
        "identifier_9": "923456789",
        "name": "Test Customer",
        "identifier_3or4": "123",
    }


@pytest.mark.customer
class TestCustomerService:
    def test_create_customer(self, customer_service, sample_customer_data):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
            identifier_3or4=sample_customer_data["identifier_3or4"],
        )

        customer = customer_service.get_customer(customer_id)
        assert customer is not None
        assert customer.identifier_9 == sample_customer_data["identifier_9"]
        assert customer.name == sample_customer_data["name"]
        assert customer.is_active is True
        assert len(
            AuditService.get_entries(
                entity_type="customer",
                entity_id=customer_id,
                operation="create_customer",
            )
        ) == 1

    def test_get_customer_missing_returns_none(self, customer_service):
        assert customer_service.get_customer(999999) is None

    def test_create_customer_invalid_identifier(self, customer_service):
        with pytest.raises(ValidationException):
            customer_service.create_customer(
                identifier_9="12345",
                name="Test Customer",
            )

    def test_update_customer(self, customer_service, sample_customer_data):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )

        new_name = "Updated Customer Name"
        customer_service.update_customer(customer_id, name=new_name)

        customer = customer_service.get_customer(customer_id)
        assert customer.name == new_name

    def test_delete_customer_archives_and_hides_from_default_listing(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
            identifier_3or4=sample_customer_data["identifier_3or4"],
        )

        customer_service.delete_customer(customer_id)

        archived_customer = customer_service.get_customer(customer_id)
        assert archived_customer is not None
        assert archived_customer.is_active is False
        assert archived_customer.deleted_at is not None
        assert customer_service.get_all_customers() == []
        assert len(customer_service.get_all_customers(active_only=False)) == 1
        assert len(
            AuditService.get_entries(
                entity_type="customer",
                entity_id=customer_id,
                operation="delete_customer",
            )
        ) == 1

    def test_restore_customer_reactivates_visibility(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )
        customer_service.delete_customer(customer_id)

        customer_service.restore_customer(customer_id)

        restored_customer = customer_service.get_customer(customer_id)
        assert restored_customer is not None
        assert restored_customer.is_active is True
        assert restored_customer.deleted_at is None
        assert [customer.id for customer in customer_service.get_all_customers()] == [
            customer_id
        ]
        assert len(
            AuditService.get_entries(
                entity_type="customer",
                entity_id=customer_id,
                operation="restore_customer",
            )
        ) == 1

    def test_search_customers_excludes_archived_by_default(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )
        customer_service.delete_customer(customer_id)

        assert customer_service.search_customers("Test") == []
        results = customer_service.search_customers("Test", active_only=False)
        assert [customer.id for customer in results] == [customer_id]

    def test_get_customer_purchase_history(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )

        history = customer_service.get_customer_purchase_history(customer_id)
        assert len(history) == 0

    def test_validate_identifiers(self, customer_service):
        assert (
            customer_service.validate_identifier("923456789", "identifier_9")
            == "923456789"
        )
        assert customer_service.validate_identifier("123", "identifier_3or4") == "123"
        assert customer_service.validate_identifier("1234", "identifier_3or4") == "1234"

        with pytest.raises(ValidationException):
            customer_service.validate_identifier("12345678", "identifier_9")
        with pytest.raises(ValidationException):
            customer_service.validate_identifier("12", "identifier_3or4")

    def test_delete_customer_marks_row_in_database(self, customer_service):
        customer_id = customer_service.create_customer("923456780", "Archive Target")

        customer_service.delete_customer(customer_id)

        row = DatabaseManager.fetch_one(
            "SELECT is_active, deleted_at FROM customers WHERE id = ?",
            (customer_id,),
        )
        assert row["is_active"] == 0
        assert row["deleted_at"] is not None

    def test_restore_customer_missing_id_raises(self, customer_service):
        with pytest.raises(NotFoundException):
            customer_service.restore_customer(999)

    def test_update_customer_missing_id_raises_not_found(self, customer_service):
        with pytest.raises(NotFoundException):
            customer_service.update_customer(999999, name="No Existe")

    def test_create_customer_emits_customer_added_once(
        self, customer_service, sample_customer_data
    ):
        payloads, handler = capture_signal(event_system.customer_added)

        try:
            customer_id = customer_service.create_customer(
                identifier_9=sample_customer_data["identifier_9"],
                name=sample_customer_data["name"],
                identifier_3or4=sample_customer_data["identifier_3or4"],
            )

            assert payloads == [customer_id]
        finally:
            event_system.customer_added.disconnect(handler)

    def test_update_customer_emits_customer_updated_once(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )
        payloads, handler = capture_signal(event_system.customer_updated)

        try:
            customer_service.update_customer(customer_id, name="Cliente Actualizado")

            assert payloads == [customer_id]
        finally:
            event_system.customer_updated.disconnect(handler)

    def test_delete_customer_emits_customer_deleted_once(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )
        payloads, handler = capture_signal(event_system.customer_deleted)

        try:
            customer_service.delete_customer(customer_id)

            assert payloads == [customer_id]
        finally:
            event_system.customer_deleted.disconnect(handler)

    def test_restore_customer_emits_customer_updated_once(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )
        customer_service.delete_customer(customer_id)
        payloads, handler = capture_signal(event_system.customer_updated)

        try:
            customer_service.restore_customer(customer_id)

            assert payloads == [customer_id]
        finally:
            event_system.customer_updated.disconnect(handler)
