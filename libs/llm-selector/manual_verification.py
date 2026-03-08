#!/usr/bin/env python
"""Manual verification script to demonstrate round-robin sequence maintenance."""

import sys
sys.path.insert(0, 'src')

from llm_selector.selector import LLMSelector

def print_separator():
    print("\n" + "="*80 + "\n")

def main():
    print("Manual Verification: Round-Robin Sequence Maintenance")
    print("="*80)

    selector = LLMSelector(as_equal_as_possible=True)

    print("\nScenario: Demonstrate that round-robin maintains logical sequence")
    print("gpt-4.1 has 4 providers in config order:")
    print("  [0] openai-gpt-4.1")
    print("  [1] azure-aueast-gpt-4.1")
    print("  [2] azure-northcentralus-gpt-4.1")
    print("  [3] azure-southcentralus-gpt-4.1")

    print_separator()

    # Select first two providers
    print("Step 1: Select first provider")
    r1 = selector.suggest_provider("gpt-4.1")
    provider_1 = r1["provider"]["model_id"]
    print(f"  Selected: {provider_1}")
    print(f"  Last used: openai-gpt-4.1")

    print("\nStep 2: Select second provider")
    r2 = selector.suggest_provider("gpt-4.1")
    provider_2 = r2["provider"]["model_id"]
    print(f"  Selected: {provider_2}")
    print(f"  Last used: azure-aueast-gpt-4.1")

    print_separator()

    # Fail first provider
    print("Step 3: Provider [0] openai fails with 429 (enters cooldown)")
    selector.last_suggested["gpt-4.1"] = provider_1
    retry_result = selector.retry_suggestion("gpt-4.1", status_code=429)
    retry_provider = retry_result["provider"]["model_id"]
    print(f"  Available providers: [1, 2, 3]")
    print(f"  Last used was: azure-aueast-gpt-4.1 (position 1)")
    print(f"  Next in sequence: position 2")
    print(f"  Selected: {retry_provider}")
    print(f"  ✓ Correctly selected azure-northcentralus-gpt-4.1 (no skip!)")

    print_separator()

    # Continue sequence
    print("Step 4: Select next provider")
    r3 = selector.suggest_provider("gpt-4.1")
    provider_3 = r3["provider"]["model_id"]
    print(f"  Last used was: azure-northcentralus-gpt-4.1 (position 2)")
    print(f"  Next in sequence: position 3")
    print(f"  Selected: {provider_3}")
    print(f"  ✓ Correctly selected azure-southcentralus-gpt-4.1")

    print_separator()

    # Wrap around
    print("Step 5: Wrap around (openai still in cooldown)")
    r4 = selector.suggest_provider("gpt-4.1")
    provider_4 = r4["provider"]["model_id"]
    print(f"  Last used was: azure-southcentralus-gpt-4.1 (position 3)")
    print(f"  Next in sequence: position 0 (wrap)")
    print(f"  But position 0 (openai) is in cooldown, skip to position 1")
    print(f"  Selected: {provider_4}")
    print(f"  ✓ Correctly wrapped to azure-aueast-gpt-4.1")

    print_separator()

    # Verify sequence
    print("Verification Summary:")
    print(f"  Selection 1: {provider_1} (openai) ✓")
    print(f"  Selection 2: {provider_2} (azure-aueast) ✓")
    print(f"  Retry after fail: {retry_provider} (azure-northcentralus) ✓ - No skip!")
    print(f"  Selection 3: {provider_3} (azure-southcentralus) ✓")
    print(f"  Selection 4: {provider_4} (azure-aueast) ✓ - Correct wrap!")

    # Check assertions
    assert "openai" in provider_1
    assert "aueast" in provider_2
    assert "northcentralus" in retry_provider, f"Expected northcentralus, got {retry_provider}"
    assert "southcentralus" in provider_3, f"Expected southcentralus, got {provider_3}"
    assert provider_4 == provider_2, f"Expected wrap to {provider_2}, got {provider_4}"

    print("\n✅ All assertions passed! Round-robin sequence is maintained correctly.")
    print_separator()

if __name__ == "__main__":
    main()
