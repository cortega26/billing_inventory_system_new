import pytest
from PySide6.QtCore import QObject, Signal
from utils.system.event_system import EventSystem
from utils.exceptions import AppException

class TestEventSystem:
    @pytest.fixture
    def event_system(self):
        """Create a fresh event system instance for each test"""
        event_system = EventSystem()
        yield event_system
        # Cleanup
        event_system.clear_all_connections()

    def test_signal_creation(self, event_system):
        """Test that signals are properly created"""
        assert hasattr(event_system, 'product_added')
        assert hasattr(event_system, 'product_updated')
        assert hasattr(event_system, 'product_deleted')
        assert hasattr(event_system, 'sale_completed')
        assert hasattr(event_system, 'purchase_completed')
        assert hasattr(event_system, 'inventory_updated')

    def test_signal_connection(self, event_system):
        """Test connecting to signals"""
        called = False

        def handler():
            nonlocal called
            called = True

        event_system.product_added.connect(handler)
        event_system.product_added.emit()
        
        assert called

    def test_signal_disconnection(self, event_system):
        """Test disconnecting from signals"""
        called = False

        def handler():
            nonlocal called
            called = True

        event_system.product_added.connect(handler)
        event_system.product_added.disconnect(handler)
        event_system.product_added.emit()
        
        assert not called

    def test_multiple_handlers(self, event_system):
        """Test multiple handlers for the same signal"""
        call_count = 0

        def handler1():
            nonlocal call_count
            call_count += 1

        def handler2():
            nonlocal call_count
            call_count += 1

        event_system.product_added.connect(handler1)
        event_system.product_added.connect(handler2)
        event_system.product_added.emit()
        
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

        def handler():
            nonlocal called
            called = True

        event_system.product_added.connect(handler)
        event_system.clear_all_connections()
        event_system.product_added.emit()
        
        assert not called

    def test_error_handling(self, event_system):
        """Test error handling in signal handlers"""
        def failing_handler():
            raise Exception("Test error")

        event_system.product_added.connect(failing_handler)
        # Should not raise exception
        event_system.product_added.emit()

    def test_signal_order(self, event_system):
        """Test that signals are handled in order"""
        order = []

        def handler1():
            order.append(1)

        def handler2():
            order.append(2)

        event_system.product_added.connect(handler1)
        event_system.product_added.connect(handler2)
        event_system.product_added.emit()
        
        assert order == [1, 2]

    def test_conditional_events(self, event_system):
        """Test conditional event handling"""
        result = {}

        def conditional_handler(data):
            nonlocal result
            if data.get('important'):
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
        class ComponentA(QObject):
            def __init__(self, event_system):
                super().__init__()
                self.event_system = event_system
                self.received = False
                self.event_system.product_added.connect(self.handle_product_added)

            def handle_product_added(self):
                self.received = True

        class ComponentB(QObject):
            def __init__(self, event_system):
                super().__init__()
                self.event_system = event_system

            def add_product(self):
                self.event_system.product_added.emit()

        component_a = ComponentA(event_system)
        component_b = ComponentB(event_system)
        
        component_b.add_product()
        assert component_a.received

    def test_event_chaining(self, event_system):
        """Test chaining of events"""
        chain_complete = False

        def handler1():
            event_system.product_updated.emit()

        def handler2():
            nonlocal chain_complete
            chain_complete = True

        event_system.product_added.connect(handler1)
        event_system.product_updated.connect(handler2)
        
        event_system.product_added.emit()
        assert chain_complete

    def test_event_system_singleton(self):
        """Test that event system behaves like a singleton"""
        event_system1 = EventSystem()
        event_system2 = EventSystem()
        
        called = False

        def handler():
            nonlocal called
            called = True

        event_system1.product_added.connect(handler)
        event_system2.product_added.emit()
        
        assert called

    def test_performance(self, event_system):
        """Test performance with many handlers"""
        call_count = 0

        def handler():
            nonlocal call_count
            call_count += 1

        # Connect many handlers
        for _ in range(100):
            event_system.product_added.connect(handler)

        event_system.product_added.emit()
        assert call_count == 100 