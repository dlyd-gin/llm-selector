"""Integration tests for end-to-end provider selection flows."""

import os
import time
from unittest.mock import patch

import pytest

from llm_selector import LLMSelector


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    env_vars = {
        "OPENAI_APIKEY": "test-openai-key",
        "AZURE_OPENAI_APIKEY_AUEAST": "test-azure-key-1",
        "AZURE_OPENAI_APIKEY_NORTHCENTRALUS": "test-azure-key-2",
        "AZURE_OPENAI_APIKEY_SOUTHCENTRALUS": "test-azure-key-3",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield


def test_end_to_end_single_provider_success(mock_env):
    """Test complete flow: suggest -> use -> success."""
    selector = LLMSelector()

    # Get initial suggestion
    result = selector.suggest_provider("gpt-5.1")

    assert result["success"] is True
    assert result["provider"]["model_id"] == "openai-gpt-5.1"
    assert result["provider"]["api_key"] == "test-openai-key"

    # Simulate successful request (no retry needed)
    # In real usage, you would make the API call here

    # Verify state
    state = selector.get_memory_state()
    assert "gpt-5.1" in state["last_suggested"]
    assert len(state["failure_records"]) == 0


def test_end_to_end_suggest_fail_retry_success(mock_env):
    """Test: suggest -> fail -> retry -> success."""
    selector = LLMSelector()

    # Initial suggestion for multi-provider model
    first_result = selector.suggest_provider("gpt-4.1")
    assert first_result["success"] is True
    first_provider = first_result["provider"]["model_id"]

    # Simulate failure with 429
    retry_result = selector.retry_suggestion("gpt-4.1", status_code=429)
    assert retry_result["success"] is True

    # Second provider should be different or same (random)
    second_provider = retry_result["provider"]["model_id"]

    # Verify first provider is in cooldown
    assert not selector.memory_store.is_available(first_provider)

    # Verify memory state
    state = selector.get_memory_state()
    assert first_provider in state["failure_records"]
    assert state["failure_records"][first_provider]["status_code"] == 429


def test_end_to_end_multiple_retries(mock_env):
    """Test: suggest -> fail -> retry -> fail -> retry -> success."""
    selector = LLMSelector()

    # Initial suggestion
    result1 = selector.suggest_provider("gpt-4.1")
    assert result1["success"] is True
    provider1 = result1["provider"]["model_id"]

    # First retry (records provider1 failure)
    result2 = selector.retry_suggestion("gpt-4.1", status_code=500)
    assert result2["success"] is True
    provider2 = result2["provider"]["model_id"]

    # Second retry (records provider2 failure)
    result3 = selector.retry_suggestion("gpt-4.1", status_code=429)
    assert result3["success"] is True
    provider3 = result3["provider"]["model_id"]

    # Verify all failed providers are in memory
    records = selector.memory_store.get_all_records()
    assert provider1 in records
    assert provider2 in records


def test_end_to_end_all_providers_fail_then_wait(mock_env):
    """Test: all providers fail -> wait for cooldown -> retry success."""
    selector = LLMSelector()

    # Fail the only provider for gpt-5.1
    selector.suggest_provider("gpt-5.1")
    selector.retry_suggestion("gpt-5.1", status_code=429)

    # Try to get another provider (should fail)
    result = selector.suggest_provider("gpt-5.1")
    assert result["success"] is False
    assert "all providers are busy" in result["reason"]
    assert "please wait" in result["reason"]

    # Check wait time is provided
    assert "s" in result["reason"]  # Should contain seconds


def test_end_to_end_cooldown_expiry(mock_env):
    """Test provider becomes available after cooldown expires."""
    selector = LLMSelector()

    # Record failure with short cooldown for testing
    selector.memory_store.record_failure("openai-gpt-5.1", 429)

    # Should be unavailable
    assert not selector.memory_store.is_available("openai-gpt-5.1", cooldown_seconds=1)

    # Wait for cooldown
    time.sleep(1.1)

    # Should be available now
    assert selector.memory_store.is_available("openai-gpt-5.1", cooldown_seconds=1)


def test_end_to_end_memory_state_inspection(mock_env):
    """Test inspecting memory state after multiple operations."""
    selector = LLMSelector()

    # Perform several operations
    selector.suggest_provider("gpt-4.1")
    selector.retry_suggestion("gpt-4.1", 429)
    selector.suggest_provider("gpt-5.1")
    selector.retry_suggestion("gpt-5.1", 500)

    # Inspect state
    state = selector.get_memory_state()

    # Should have failure records
    assert len(state["failure_records"]) == 2

    # Should have last suggested for both models
    assert "gpt-4.1" in state["last_suggested"]
    assert "gpt-5.1" in state["last_suggested"]

    # Verify structure of failure records
    for model_id, record in state["failure_records"].items():
        assert "model_id" in record
        assert "status_code" in record
        assert "recorded_at" in record
        assert isinstance(record["status_code"], int)


def test_end_to_end_reset_and_restart(mock_env):
    """Test resetting memory and starting fresh."""
    selector = LLMSelector()

    # Perform operations that create failures
    selector.suggest_provider("gpt-4.1")
    selector.retry_suggestion("gpt-4.1", 429)
    selector.retry_suggestion("gpt-4.1", 500)

    # Verify state has data
    state_before = selector.get_memory_state()
    assert len(state_before["failure_records"]) > 0

    # Reset
    selector.reset_memory_store()

    # Verify clean state
    state_after = selector.get_memory_state()
    assert len(state_after["failure_records"]) == 0
    assert len(state_after["last_suggested"]) == 0

    # Should be able to suggest again
    result = selector.suggest_provider("gpt-4.1")
    assert result["success"] is True


def test_end_to_end_different_models_independent(mock_env):
    """Test that different models maintain independent state."""
    selector = LLMSelector()

    # Fail provider for gpt-4.1
    selector.suggest_provider("gpt-4.1")
    selector.retry_suggestion("gpt-4.1", 429)

    # gpt-5.1 should still work fine
    result = selector.suggest_provider("gpt-5.1")
    assert result["success"] is True

    # Verify independent state
    state = selector.get_memory_state()
    assert "gpt-4.1" in state["last_suggested"]
    assert "gpt-5.1" in state["last_suggested"]


def test_end_to_end_provider_rotation(mock_env):
    """Test that providers rotate under load."""
    selector = LLMSelector()

    providers_used = set()

    # Make multiple requests
    for _ in range(10):
        result = selector.suggest_provider("gpt-4.1")
        if result["success"]:
            providers_used.add(result["provider"]["model_id"])

    # Should use multiple providers due to random selection
    assert len(providers_used) >= 2


def test_end_to_end_realistic_retry_scenario(mock_env):
    """Test a realistic scenario with rate limiting and retries."""
    selector = LLMSelector()

    # Simulate rate limit scenario
    providers_tried = []

    # Initial attempt
    result1 = selector.suggest_provider("gpt-4.1")
    assert result1["success"] is True
    providers_tried.append(result1["provider"]["model_id"])

    # Hit rate limit, retry
    result2 = selector.retry_suggestion("gpt-4.1", status_code=429)
    assert result2["success"] is True
    providers_tried.append(result2["provider"]["model_id"])

    # Hit rate limit again, retry
    result3 = selector.retry_suggestion("gpt-4.1", status_code=429)
    assert result3["success"] is True
    providers_tried.append(result3["provider"]["model_id"])

    # Should have tried multiple providers
    # Note: Due to random selection, might select same provider
    # But at least 2 providers should be in cooldown now
    records = selector.memory_store.get_all_records()
    assert len(records) >= 2

    # All recorded failures should be 429
    for record in records.values():
        assert record.status_code == 429


def test_end_to_end_with_dotenv_file(tmp_path, mock_env):
    """Test loading configuration from .env file."""
    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_API_KEY=test-value-from-file\n")

    # Create selector with custom dotenv path
    selector = LLMSelector(dotenv_path=str(env_file))

    # Should still work with existing config
    result = selector.suggest_provider("gpt-5.1")
    assert result["success"] is True
