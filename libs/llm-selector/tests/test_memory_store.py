"""Tests for memory store functionality."""

import time
from datetime import datetime, timedelta

import pytest

from llm_selector.memory_store import MemoryStore


@pytest.fixture
def memory_store():
    """Create a fresh memory store for each test."""
    return MemoryStore()


@pytest.fixture
def sample_model_mappings():
    """Sample model mappings for testing."""
    return {
        "test-model": [
            {"model_id": "provider-1", "model": "test/model-1"},
            {"model_id": "provider-2", "model": "test/model-2"},
            {"model_id": "provider-3", "model": "test/model-3"}
        ]
    }


def test_record_failure_new_provider(memory_store):
    """Test recording a failure for a new provider."""
    memory_store.record_failure("provider-1", 429)

    records = memory_store.get_all_records()
    assert "provider-1" in records
    assert records["provider-1"].status_code == 429
    assert records["provider-1"].model_id == "provider-1"


def test_is_available_new_provider(memory_store):
    """Test that new providers are available."""
    assert memory_store.is_available("provider-1") is True


def test_is_available_after_failure(memory_store):
    """Test that provider is unavailable immediately after failure."""
    memory_store.record_failure("provider-1", 500)
    assert memory_store.is_available("provider-1") is False


def test_is_available_after_cooldown(memory_store):
    """Test that provider becomes available after cooldown."""
    # Record failure with custom cooldown
    memory_store.record_failure("provider-1", 429)

    # Should be unavailable with 1 second cooldown
    assert memory_store.is_available("provider-1", cooldown_seconds=1) is False

    # Wait for cooldown
    time.sleep(1.1)

    # Should be available now
    assert memory_store.is_available("provider-1", cooldown_seconds=1) is True


def test_record_failure_updates_only_after_60s(memory_store):
    """Test that failure record only updates if >60s elapsed."""
    # Record initial failure
    memory_store.record_failure("provider-1", 429)
    first_record = memory_store.get_all_records()["provider-1"]
    first_timestamp = first_record.recorded_at

    # Try to record again immediately
    memory_store.record_failure("provider-1", 500)
    second_record = memory_store.get_all_records()["provider-1"]

    # Timestamp should NOT have changed
    assert second_record.recorded_at == first_timestamp
    assert second_record.status_code == 429  # Original status code preserved


def test_get_unavailable_providers(memory_store, sample_model_mappings):
    """Test getting list of unavailable providers."""
    # Record failures for two providers
    memory_store.record_failure("provider-1", 429)
    memory_store.record_failure("provider-2", 500)

    unavailable = memory_store.get_unavailable_providers(
        "test-model",
        sample_model_mappings
    )

    assert len(unavailable) == 2
    assert "provider-1" in unavailable
    assert "provider-2" in unavailable
    assert "provider-3" not in unavailable


def test_get_unavailable_providers_invalid_model(memory_store, sample_model_mappings):
    """Test get_unavailable_providers with invalid model name."""
    unavailable = memory_store.get_unavailable_providers(
        "invalid-model",
        sample_model_mappings
    )
    assert unavailable == []


def test_calculate_shortest_wait(memory_store, sample_model_mappings):
    """Test calculating shortest wait time."""
    # Record failure with 1 second cooldown for testing
    memory_store.record_failure("provider-1", 429)

    # Calculate wait time with 2 second cooldown
    wait_time = memory_store.calculate_shortest_wait(
        "test-model",
        sample_model_mappings,
        cooldown_seconds=2
    )

    # Should be approximately 2 seconds (minus small elapsed time)
    assert 1 <= wait_time <= 2


def test_calculate_shortest_wait_multiple_providers(memory_store, sample_model_mappings):
    """Test shortest wait with multiple failed providers."""
    # Record failures at different times
    memory_store.record_failure("provider-1", 429)
    time.sleep(0.5)
    memory_store.record_failure("provider-2", 500)

    # Calculate with 1 second cooldown
    wait_time = memory_store.calculate_shortest_wait(
        "test-model",
        sample_model_mappings,
        cooldown_seconds=1
    )

    # Should return time for provider-1 (recorded first)
    assert 0 <= wait_time <= 1


def test_calculate_shortest_wait_no_failures(memory_store, sample_model_mappings):
    """Test shortest wait when no providers have failed."""
    wait_time = memory_store.calculate_shortest_wait(
        "test-model",
        sample_model_mappings
    )
    assert wait_time == 0


def test_get_all_records(memory_store):
    """Test getting all failure records."""
    memory_store.record_failure("provider-1", 429)
    memory_store.record_failure("provider-2", 500)

    records = memory_store.get_all_records()

    assert len(records) == 2
    assert "provider-1" in records
    assert "provider-2" in records


def test_reset(memory_store):
    """Test resetting the memory store."""
    memory_store.record_failure("provider-1", 429)
    memory_store.record_failure("provider-2", 500)

    assert len(memory_store.get_all_records()) == 2

    memory_store.reset()

    assert len(memory_store.get_all_records()) == 0
    assert memory_store.is_available("provider-1") is True


def test_cooldown_custom_duration(memory_store):
    """Test custom cooldown duration."""
    memory_store.record_failure("provider-1", 429)

    # With 120 second cooldown, should be unavailable
    assert memory_store.is_available("provider-1", cooldown_seconds=120) is False

    # With 0 second cooldown, should be available
    assert memory_store.is_available("provider-1", cooldown_seconds=0) is True
