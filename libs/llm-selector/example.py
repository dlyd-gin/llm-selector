"""Example usage of the llm-selector library."""

import os
import time
from llm_selector import LLMSelector


def main():
    """Demonstrate provider selector usage."""

    # Set up some mock environment variables for testing
    os.environ["OPENAI_APIKEY"] = "sk-test-key-12345"
    os.environ["AZURE_OPENAI_APIKEY_AUEAST"] = "azure-test-key-1"
    os.environ["AZURE_OPENAI_APIKEY_NORTHCENTRALUS"] = "azure-test-key-2"
    os.environ["AZURE_OPENAI_APIKEY_SOUTHCENTRALUS"] = "azure-test-key-3"

    print("=" * 70)
    print("LLM Selector - Example Usage")
    print("=" * 70)
    print()

    # Initialize selector
    selector = LLMSelector()

    # Example 1: Simple provider suggestion
    print("Example 1: Get provider suggestion for gpt-5.1")
    print("-" * 70)
    result = selector.suggest_provider("gpt-5.1")
    if result["success"]:
        provider = result["provider"]
        print(f"✓ Provider selected: {provider['model_id']}")
        print(f"  Model: {provider['model']}")
        print(f"  API Base: {provider['api_base']}")
        print(f"  API Key: {provider['api_key'][:20]}...")
    else:
        print(f"✗ Error: {result['reason']}")
    print()

    # Example 2: Multi-provider model with retries
    print("Example 2: Multi-provider model with failure and retry")
    print("-" * 70)

    # Get initial provider for gpt-4.1 (has 4 providers)
    result1 = selector.suggest_provider("gpt-4.1")
    print(f"✓ First provider: {result1['provider']['model_id']}")

    # Simulate a failure (e.g., rate limit)
    print("  Simulating 429 rate limit error...")
    result2 = selector.retry_suggestion("gpt-4.1", status_code=429)
    print(f"✓ Retry provider: {result2['provider']['model_id']}")

    # Check memory state
    state = selector.get_memory_state()
    print(f"  Failure records: {len(state['failure_records'])}")
    print()

    # Example 3: Inspect memory state
    print("Example 3: Memory state inspection")
    print("-" * 70)
    state = selector.get_memory_state()
    print("Failure records:")
    for model_id, record in state['failure_records'].items():
        print(f"  • {model_id}: status {record['status_code']} at {record['recorded_at']}")
    print(f"\nLast suggested providers:")
    for model, provider_id in state['last_suggested'].items():
        print(f"  • {model} → {provider_id}")
    print()

    # Example 4: All providers busy scenario
    print("Example 4: All providers busy scenario")
    print("-" * 70)

    # Fail all providers for gpt-5.1
    selector.suggest_provider("gpt-5.1")
    selector.retry_suggestion("gpt-5.1", status_code=429)

    # Try to get another provider
    result = selector.suggest_provider("gpt-5.1")
    if not result["success"]:
        print(f"✗ {result['reason']}")
    print()

    # Example 5: Reset memory store
    print("Example 5: Reset memory store")
    print("-" * 70)
    print(f"Failure records before reset: {len(selector.get_memory_state()['failure_records'])}")
    selector.reset_memory_store()
    print(f"Failure records after reset: {len(selector.get_memory_state()['failure_records'])}")
    print("✓ Memory store cleared!")
    print()

    # Example 6: Claude Sonnet with special headers
    print("Example 6: Claude Sonnet with Anthropic beta header")
    print("-" * 70)
    result = selector.suggest_provider("claude-sonnet-4-5")
    if result["success"]:
        provider = result["provider"]
        print(f"✓ Provider: {provider['model_id']}")
        print(f"  Model: {provider['model']}")
        print(f"  AWS Region: {provider['aws_region_name']}")
        print(f"  Anthropic Beta: {provider['anthropic_beta']}")
    print()

    # Example 7: Invalid model name
    print("Example 7: Invalid model name handling")
    print("-" * 70)
    result = selector.suggest_provider("invalid-model-xyz")
    if not result["success"]:
        print(f"✗ {result['reason']}")
    print()

    # Example 8: Round-robin selection for equal distribution
    print("Example 8: Round-robin selection with as_equal_as_possible=True")
    print("-" * 70)

    rr_selector = LLMSelector(as_equal_as_possible=True)

    print("Selecting gpt-4.1 provider 8 times (4 providers available):")
    selections = []
    for i in range(8):
        result = rr_selector.suggest_provider("gpt-4.1")
        if result["success"]:
            provider_id = result["provider"]["model_id"]
            selections.append(provider_id)
            print(f"  {i+1}. {provider_id}")

    print(f"\n✓ First 4 unique providers: {len(set(selections[:4]))}")
    print(f"✓ Pattern repeats: {selections[:4] == selections[4:8]}")
    print()

    print("=" * 70)
    print("Example completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
