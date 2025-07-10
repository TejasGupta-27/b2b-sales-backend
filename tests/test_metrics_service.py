import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config
import tests.mock_config
sys.modules['config'] = tests.mock_config

# Mock db dependencies
class MockBase:
    pass

class MockMessage:
    pass

class MockLead:
    pass

class LeadStatus:
    NEW = "new"
    ACTIVE = "active"
    QUALIFIED = "qualified"

class MockDatabase:
    Base = MockBase
    def get_db():
        pass

MockModels = type('MockModels', (), {
    'Base': MockBase,
    'ChatMessage': MockMessage,
    'Lead': MockLead,
    'LeadStatus': LeadStatus
})

sys.modules['db.database'] = MockDatabase
sys.modules['db.models'] = MockModels

from prometheus_client import REGISTRY, CollectorRegistry
from services.metrics_service import MetricsService, b2b_conversation_duration_seconds

@pytest.fixture
def metrics_service():
    return MetricsService()

@pytest.fixture(autouse=True)
def clear_metrics():
    """Clear all metrics before each test"""
    # Create a new clean registry for each test
    global REGISTRY
    REGISTRY = CollectorRegistry()
    yield
    # Clean up after test
    REGISTRY = CollectorRegistry()

def test_record_conversation_duration_basic(metrics_service):
    """Test basic conversation duration recording"""
    metrics_service.record_conversation_duration(
        duration=120.5,  # 2 minutes
        language="en",
        status="completed"
    )
    
    # Get the metric
    samples = list(b2b_conversation_duration_seconds.collect()[0].samples)
    # Get count from histogram
    duration_count = [s for s in samples if s.labels['language'] == 'en' and s.labels['status'] == 'completed' and s.name.endswith('_count')][0]
    
    assert duration_count.value == 1  # Histogram count should be 1
    assert duration_count.labels['language'] == 'en'
    assert duration_count.labels['status'] == 'completed'

def test_record_conversation_duration_multiple_languages(metrics_service):
    """Test recording durations for multiple languages"""
    # Record conversations in different languages
    metrics_service.record_conversation_duration(60.0, "en", "completed")
    metrics_service.record_conversation_duration(120.0, "ja", "completed")
    metrics_service.record_conversation_duration(180.0, "es", "completed")
    
    # Get all metrics
    samples = list(b2b_conversation_duration_seconds.collect()[0].samples)
    
    # Check each language has a record
    languages = set(s.labels['language'] for s in samples)
    assert "en" in languages
    assert "ja" in languages
    assert "es" in languages

def test_record_conversation_duration_different_statuses(metrics_service):
    """Test recording durations with different statuses"""
    # Record conversations with different statuses
    metrics_service.record_conversation_duration(60.0, "en", "completed")
    metrics_service.record_conversation_duration(60.0, "en", "abandoned")
    metrics_service.record_conversation_duration(60.0, "en", "ongoing")
    
    # Get all metrics
    samples = list(b2b_conversation_duration_seconds.collect()[0].samples)
    
    # Check each status has a record
    statuses = set(s.labels['status'] for s in samples)
    assert "completed" in statuses
    assert "abandoned" in statuses
    assert "ongoing" in statuses

def test_record_conversation_duration_error_handling(metrics_service):
    """Test error handling in conversation duration recording"""
    # These should not raise exceptions
    metrics_service.record_conversation_duration(None, "en", "completed")  # Invalid duration
    metrics_service.record_conversation_duration(-1.0, "en", "completed")  # Negative duration
    metrics_service.record_conversation_duration(60.0, None, "completed")  # Missing language
    metrics_service.record_conversation_duration(60.0, "en", None)  # Missing status

def test_record_conversation_duration_performance(metrics_service):
        """Test recording many conversation durations"""
        # Record 1000 conversations
        for i in range(1000):
            metrics_service.record_conversation_duration(
                duration=60.0,
                language="en",
                status="completed"
            )
            
        # Allow for some margin of error due to pre-existing state
            samples = list(b2b_conversation_duration_seconds.collect()[0].samples)
            en_completed = [s for s in samples if s.labels['language'] == 'en' and s.labels['status'] == 'completed' and s.name.endswith('_count')][0]
            assert abs(en_completed.value - 1000) < 5  # Should be close to 1000 conversations
