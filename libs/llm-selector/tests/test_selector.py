"""Tests for provider selector functionality."""

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


@pytest.fixture
def selector(mock_env):
    """Create a fresh selector for each test with mocked environment."""
    return LLMSelector()


@pytest.fixture
def selector_no_env():
    """Create a fresh selector without mocked environment."""
    return LLMSelector()


def test_suggest_provider_valid_model(selector, mock_env):
    """Test suggesting a provider for a valid model."""
    result = selector.suggest_provider("gpt-5.1")

    assert result["success"] is True
    assert "provider" in result
    assert result["provider"]["model_id"] == "openai-gpt-5.1"
    assert result["provider"]["api_key"] == "test-openai-key"


def test_suggest_provider_invalid_model(selector_no_env):
    """Test suggesting a provider for an invalid model."""
    result = selector_no_env.suggest_provider("invalid-model")

    assert result["success"] is False
    assert "no provider available" in result["reason"]
    assert "valid model_name" in result["reason"]


def test_suggest_provider_multiple_providers(selector, mock_env):
    """Test suggesting from multiple providers."""
    result = selector.suggest_provider("gpt-4.1")

    assert result["success"] is True
    assert "provider" in result

    # Should be one of the 4 providers
    possible_ids = [
        "openai-gpt-4.1",
        "azure-aueast-gpt-4.1",
        "azure-northcentralus-gpt-4.1",
        "azure-southcentralus-gpt-4.1"
    ]
    assert result["provider"]["model_id"] in possible_ids


def test_suggest_provider_tracks_last_suggested(selector, mock_env):
    """Test that last suggested provider is tracked."""
    result = selector.suggest_provider("gpt-5.1")

    assert "gpt-5.1" in selector.last_suggested
    assert selector.last_suggested["gpt-5.1"] == result["provider"]["model_id"]


def test_retry_suggestion_records_failure(selector, mock_env):
    """Test that retry records failure of last suggested provider."""
    # First suggestion
    first_result = selector.suggest_provider("gpt-5.1")
    first_model_id = first_result["provider"]["model_id"]

    # Retry after failure
    selector.retry_suggestion("gpt-5.1", status_code=429)

    # Check memory store has the failure
    records = selector.memory_store.get_all_records()
    assert first_model_id in records
    assert records[first_model_id].status_code == 429


def test_retry_suggestion_excludes_failed_provider(selector, mock_env):
    """Test that retry excludes the failed provider."""
    # Record a failure for one of the Azure providers
    selector.memory_store.record_failure("azure-aueast-gpt-4.1", 429)

    # Get available providers multiple times
    available_ids = set()
    for _ in range(10):
        result = selector.suggest_provider("gpt-4.1")
        if result["success"]:
            available_ids.add(result["provider"]["model_id"])

    # The failed provider should not be suggested
    assert "azure-aueast-gpt-4.1" not in available_ids


def test_all_providers_busy(selector, mock_env):
    """Test error when all providers are in cooldown."""
    # Mark all providers for gpt-5.1 as failed
    selector.memory_store.record_failure("openai-gpt-5.1", 429)

    result = selector.suggest_provider("gpt-5.1")

    assert result["success"] is False
    assert "all providers are busy" in result["reason"]
    assert "please wait" in result["reason"]


def test_environment_variable_resolution(selector, mock_env):
    """Test that environment variables are resolved correctly."""
    result = selector.suggest_provider("gpt-5.1")

    assert result["success"] is True
    # Should resolve OPENAI_APIKEY to actual value
    assert result["provider"]["api_key"] == "test-openai-key"
    assert result["provider"]["api_key"] != "OPENAI_APIKEY"


def test_environment_variable_not_found_warning(capsys):
    """Test warning when environment variable is not found."""
    # Create selector without mocked env vars
    # Warning should appear during initialization now
    selector = LLMSelector()
    result = selector.suggest_provider("gpt-5.1")

    # Should still return success but with warning captured during init
    captured = capsys.readouterr()
    if "OPENAI_APIKEY" not in os.environ:
        assert "Warning" in captured.out


def test_get_memory_state(selector, mock_env):
    """Test getting memory state."""
    # Record some failures
    selector.suggest_provider("gpt-5.1")
    selector.retry_suggestion("gpt-5.1", 429)

    state = selector.get_memory_state()

    assert "failure_records" in state
    assert "last_suggested" in state
    assert "gpt-5.1" in state["last_suggested"]


def test_reset_memory_store(selector, mock_env):
    """Test resetting the memory store."""
    # Record some failures
    selector.suggest_provider("gpt-5.1")
    selector.retry_suggestion("gpt-5.1", 429)

    # Reset
    selector.reset_memory_store()

    # Check everything is cleared
    assert len(selector.memory_store.get_all_records()) == 0
    assert len(selector.last_suggested) == 0


def test_retry_without_previous_suggestion(selector, mock_env):
    """Test retry without a previous suggestion."""
    # Call retry without calling suggest first
    result = selector.retry_suggestion("gpt-5.1", 429)

    # Should still work (no failure to record)
    assert result["success"] is True


def test_multiple_retries(selector, mock_env):
    """Test multiple consecutive retries."""
    # Initial suggestion
    selector.suggest_provider("gpt-4.1")

    # Multiple retries
    for i in range(3):
        result = selector.retry_suggestion("gpt-4.1", 429)
        if i < 3:  # First 3 should succeed (4 providers total)
            assert result["success"] is True


def test_random_selection_distribution(selector, mock_env):
    """Test that random selection uses all available providers."""
    # Reset between attempts to avoid cooldown
    selected_ids = set()

    for _ in range(20):
        selector.reset_memory_store()
        result = selector.suggest_provider("gpt-4.1")
        if result["success"]:
            selected_ids.add(result["provider"]["model_id"])

    # Should have selected multiple different providers
    assert len(selected_ids) >= 2


def test_anthropic_beta_header(selector, mock_env):
    """Test that Anthropic beta header is included."""
    result = selector.suggest_provider("claude-sonnet-4-5")

    assert result["success"] is True
    assert "aws_bedrock" in result["provider"]
    assert result["provider"]["aws_bedrock"]["anthropic_beta"] == "context-1m-2025-08-07"


def test_aws_region_name(selector, mock_env):
    """Test that AWS region name is included for Bedrock."""
    result = selector.suggest_provider("claude-sonnet-4-5")

    assert result["success"] is True
    assert "aws_bedrock" in result["provider"]
    assert result["provider"]["aws_bedrock"]["aws_region_name"] == "us-west-2"


def test_azure_api_version(selector, mock_env):
    """Test that Azure API version is included."""
    # Force selection of Azure provider
    selector.memory_store.record_failure("openai-gpt-4.1", 429)

    result = selector.suggest_provider("gpt-4.1")

    if "azure" in result["provider"]["model_id"]:
        assert "api_version" in result["provider"]
        assert result["provider"]["api_version"] == "2024-02-15-preview"


def test_error_handling_unexpected_exception(selector_no_env):
    """Test error handling for unexpected exceptions."""
    # This should trigger an error in the internal logic
    with patch.object(selector_no_env.memory_store, 'is_available', side_effect=Exception("Test error")):
        result = selector_no_env.suggest_provider("gpt-5.1")

        assert result["success"] is False
        assert "unexpected issue" in result["reason"]


def test_round_robin_selection(mock_env):
    """Test round-robin selection when as_equal_as_possible=True."""
    selector = LLMSelector(as_equal_as_possible=True)

    # Select from gpt-4.1 (4 providers) multiple times
    selections = []
    for _ in range(8):  # Two full cycles
        result = selector.suggest_provider("gpt-4.1")
        assert result["success"] is True
        selections.append(result["provider"]["model_id"])

    # Should cycle through all 4 providers twice in same order
    # First 4 should be all different
    assert len(set(selections[:4])) == 4
    # Second 4 should match first 4 (same order)
    assert selections[:4] == selections[4:8]


def test_round_robin_per_model_tracking(mock_env):
    """Test that round-robin tracking is per-model."""
    selector = LLMSelector(as_equal_as_possible=True)

    # Select from gpt-5.1 (1 provider)
    result1 = selector.suggest_provider("gpt-5.1")
    provider1 = result1["provider"]["model_id"]

    # Select from gpt-4.1 (4 providers)
    result2 = selector.suggest_provider("gpt-4.1")
    provider2 = result2["provider"]["model_id"]

    # Select from gpt-4.1 again
    result3 = selector.suggest_provider("gpt-4.1")
    provider3 = result3["provider"]["model_id"]

    # gpt-4.1 should have moved to next provider
    assert provider2 != provider3


def test_round_robin_reset(mock_env):
    """Test that round-robin indices are cleared on reset."""
    selector = LLMSelector(as_equal_as_possible=True)

    # Do some selections to advance indices
    selector.suggest_provider("gpt-4.1")
    selector.suggest_provider("gpt-4.1")

    # Reset
    selector.reset_memory_store()

    # Next selection should start from beginning again
    selections_after_reset = []
    for _ in range(4):
        result = selector.suggest_provider("gpt-4.1")
        selections_after_reset.append(result["provider"]["model_id"])

    # Should get all 4 providers
    assert len(set(selections_after_reset)) == 4


def test_round_robin_with_cooldown(mock_env):
    """Test round-robin behavior when some providers are in cooldown."""
    selector = LLMSelector(as_equal_as_possible=True)

    # Get first two providers
    result1 = selector.suggest_provider("gpt-4.1")
    provider1_id = result1["provider"]["model_id"]

    result2 = selector.suggest_provider("gpt-4.1")
    provider2_id = result2["provider"]["model_id"]

    # Fail first provider (puts it in cooldown)
    selector.last_suggested["gpt-4.1"] = provider1_id
    selector.retry_suggestion("gpt-4.1", status_code=429)

    # Continue selecting - should cycle through remaining 3 available
    selections = []
    for _ in range(6):
        result = selector.suggest_provider("gpt-4.1")
        if result["success"]:
            selections.append(result["provider"]["model_id"])

    # Should not include the failed provider
    assert provider1_id not in selections
    # Should cycle through the 3 available providers
    assert len(set(selections)) == 3


def test_round_robin_maintains_sequence_with_cooldown(mock_env):
    """Test that round-robin maintains logical sequence when providers cycle in/out."""
    selector = LLMSelector(as_equal_as_possible=True)

    # Get provider order from config
    # gpt-4.1 has 4 providers: [openai, azure-aueast, azure-northcentralus, azure-southcentralus]

    # Select first two providers
    r1 = selector.suggest_provider("gpt-4.1")
    provider_1 = r1["provider"]["model_id"]  # Should be openai-gpt-4.1

    r2 = selector.suggest_provider("gpt-4.1")
    provider_2 = r2["provider"]["model_id"]  # Should be azure-aueast-gpt-4.1

    # Fail provider_1 (puts it in cooldown)
    selector.last_suggested["gpt-4.1"] = provider_1
    retry_result = selector.retry_suggestion("gpt-4.1", status_code=429)

    # retry_suggestion should continue sequence: azure-northcentralus (3rd in config)
    # This is because last_used was provider_2, so next is provider_3
    retry_provider = retry_result["provider"]["model_id"]
    assert "northcentralus" in retry_provider, f"Expected northcentralus from retry, got {retry_provider}"

    # Next selection should get southcentralus (4th in config)
    r3 = selector.suggest_provider("gpt-4.1")
    provider_3 = r3["provider"]["model_id"]
    assert "southcentralus" in provider_3, f"Expected southcentralus, got {provider_3}"

    # Then should wrap to azure-aueast (skip openai still in cooldown)
    r4 = selector.suggest_provider("gpt-4.1")
    provider_4 = r4["provider"]["model_id"]
    assert provider_4 == provider_2, f"Expected wrap to {provider_2}, got {provider_4}"


def test_default_remains_random(mock_env):
    """Test that default behavior (as_equal_as_possible=False) remains random."""
    selector = LLMSelector(as_equal_as_possible=False)

    # This is the existing test - just verify it still works
    selected_ids = set()
    for _ in range(20):
        selector.reset_memory_store()
        result = selector.suggest_provider("gpt-4.1")
        if result["success"]:
            selected_ids.add(result["provider"]["model_id"])

    # Should have selected multiple different providers (probabilistic)
    assert len(selected_ids) >= 2


def test_suggest_provider_by_id_available(selector, mock_env):
    """Test that a valid, available model_id returns the exact provider without updating last_suggested."""
    # Advance round-robin state so we can check it is not disturbed
    selector.suggest_provider("gpt-4.1")
    last_suggested_before = selector.last_suggested.copy()

    result = selector.suggest_provider_by_id("openai-gpt-4.1")

    assert result["success"] is True
    assert result["provider"]["model_id"] == "openai-gpt-4.1"
    # last_suggested must not have been updated by suggest_provider_by_id
    assert selector.last_suggested == last_suggested_before


def test_suggest_provider_by_id_unavailable(selector, mock_env):
    """Test that a model_id in cooldown returns success=False with 'unavailable' in reason."""
    selector.memory_store.record_failure("openai-gpt-4.1", 429)

    result = selector.suggest_provider_by_id("openai-gpt-4.1")

    assert result["success"] is False
    assert "unavailable" in result["reason"]
    assert "openai-gpt-4.1" in result["reason"]


def test_suggest_provider_by_id_invalid(selector, mock_env):
    """Test that a non-existent model_id returns success=False with 'not a valid model_id' in reason."""
    result = selector.suggest_provider_by_id("nonexistent-provider-xyz")

    assert result["success"] is False
    assert "not a valid model_id" in result["reason"]
