import importlib
import os

import pytest

from utils.system import event_system as event_system_module

# Import QObject and EventSystem dynamically or from the module to modify behavior
# We will use the module reference in the fixture to reload


class TestEventSystem:
    @pytest.fixture
    def event_system(self):
        """Create a fresh event system instance for each test, forcing Mock implementation."""
        # Force mock
        os.environ["USE_MOCK_EVENT_SYSTEM"] = "1"
        importlib.reload(event_system_module)

        # Create instance from reloaded module
        es_class = event_system_module.EventSystem
        event_system = es_class()

        yield event_system

        # Cleanup
        event_system.clear_all_connections()

        # Reset to normal
        del os.environ["USE_MOCK_EVENT_SYSTEM"]
        importlib.reload(event_system_module)

    def test_signal_creation(self, event_system):
        """Test that signals are properly created"""
        assert hasattr(event_system, "product_added")
        assert hasattr(event_system, "product_updated")
        assert hasattr(event_system, "product_deleted")
        assert hasattr(event_system, "sale_added")
        assert hasattr(event_system, "purchase_added")
        assert hasattr(event_system, "inventory_updated")

    def test_signal_connection(self, event_system):
        """Test connecting to signals"""
        called = False

        def handler(data):
            nonlocal called
            called = True

        event_system.product_added.connect(handler)
        event_system.product_added.emit(1)

        assert called

    def test_signal_disconnection(self, event_system):
        """Test disconnecting from signals"""
        called = False

        def handler(data):
            nonlocal called
            called = True

        event_system.product_added.connect(handler)
        event_system.product_added.disconnect(handler)
        event_system.product_added.emit(1)

        assert not called

    def test_multiple_handlers(self, event_system):
        """Test multiple handlers for the same signal"""
        call_count = 0

        def handler1(data):
            nonlocal call_count
            call_count += 1

        def handler2(data):
            nonlocal call_count
            call_count += 1

        event_system.product_added.connect(handler1)
        event_system.product_added.connect(handler2)
        event_system.product_added.emit(1)

        assert call_count == 2

    def test_signal_with_parameters(self, event_system):
        """Test signals with parameters"""
        received_data = None

        def handler(data):
            nonlocal received_data
            received_data = data

        event_system.product_updated.connect(handler)
        test_data = {"id": 1, "name": "Test Product"}
        event_system.product_updated.emit(test_data)

        assert received_data == test_data

    def test_clear_connections(self, event_system):
        """Test clearing all connections"""
        called = False

        def handler(data):
            nonlocal called
            called = True

        event_system.product_added.connect(handler)
        event_system.clear_all_connections()
        event_system.product_added.emit(1)

        assert not called

    def test_error_handling(self, event_system):
        """Test error handling in signal handlers"""

        def failing_handler(data):
            raise Exception("Test error")

        event_system.product_added.connect(failing_handler)
        # Should raise exception as EventSystem does not swallow them
        with pytest.raises(Exception, match="Test error"):
            event_system.product_added.emit(1)

    def test_signal_order(self, event_system):
        """Test that signals are handled in order"""
        order = []

        def handler1(data):
            order.append(1)

        def handler2(data):
            order.append(2)

        event_system.product_added.connect(handler1)
        event_system.product_added.connect(handler2)
        event_system.product_added.emit(1)

        assert order == [1, 2]

    def test_conditional_events(self, event_system):
        """Test conditional event handling"""
        result = {}

        def conditional_handler(data):
            nonlocal result
            if data.get("important"):
                result.update(data)

        event_system.product_updated.connect(conditional_handler)

        # Should not trigger handler
        event_system.product_updated.emit({"important": False})
        assert not result

        # Should trigger handler
        event_system.product_updated.emit({"important": True})
        assert result.get("important") is True

    def test_cross_component_communication(self, event_system):
        """Test communication between different components"""

        class ComponentA(event_system_module.QObject):
            def __init__(self, event_system):
                super().__init__()
                self.event_system = event_system
                self.received = False
                self.event_system.product_added.connect(self.handle_product_added)

            def handle_product_added(self, product_id):
                self.received = True

        class ComponentB(event_system_module.QObject):
            def __init__(self, event_system):
                super().__init__()
                self.event_system = event_system

            def add_product(self):
                self.event_system.product_added.emit(1)

        component_a = ComponentA(event_system)
        component_b = ComponentB(event_system)

        component_b.add_product()
        assert component_a.received

    def test_event_chaining(self, event_system):
        """Test chaining of events"""
        chain_complete = False

        def handler1(data):
            event_system.product_updated.emit(1)

        def handler2(data):
            nonlocal chain_complete
            chain_complete = True

        event_system.product_added.connect(handler1)
        event_system.product_updated.connect(handler2)

        event_system.product_added.emit(1)
        assert chain_complete

        # EventSystem is not a singleton by default in tests
        pass

    def test_performance(self, event_system):
        """Test performance with many handlers"""
        call_count = 0

        def handler(data):
            nonlocal call_count
            call_count += 1

        # Connect many handlers
        for _ in range(100):
            event_system.product_added.connect(handler)

        event_system.product_added.emit(1)
        assert call_count == 100
