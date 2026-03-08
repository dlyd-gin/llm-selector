"""Sample client demonstrating llm_selector usage after pip install."""

import os
import sys
import argparse
from pathlib import Path
from llm_selector import LLMSelector
from openai import OpenAI, AzureOpenAI, APIError, APITimeoutError, APIConnectionError


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sample Client - LLM Selector Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --env .env
  %(prog)s -e C:\\path\\to\\.env
  %(prog)s

Default behavior:
  If no --env argument is provided, the client will look for .env in the current directory.
        """
    )
    parser.add_argument(
        '--env', '-e',
        type=str,
        default='./.env',
        help='Path to the .env file containing API keys (default: ./.env)'
    )
    return parser.parse_args()


def get_bundled_env_example():
    """Get the bundled .env.example content for display."""
    try:
        # When packaged with PyInstaller, files are in sys._MEIPASS
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent

        env_example_path = base_path / '.env.example'

        if env_example_path.exists():
            with open(env_example_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return "# .env.example file not found in the bundle"
    except Exception as e:
        return f"# Error reading .env.example: {str(e)}"


def validate_env_file(env_path: str) -> bool:
    """
    Validate that the .env file exists.
    If not, display the .env.example template and exit.

    Args:
        env_path: Path to the .env file

    Returns:
        True if file exists, False otherwise (will exit in this case)
    """
    env_file = Path(env_path)

    if not env_file.exists():
        print("=" * 80)
        print("ERROR: .env file not found!")
        print("=" * 80)
        print()
        print(f"The specified .env file does not exist:")
        print(f"  {env_file.absolute()}")
        print()
        print("To use this application, you need to create a .env file with your API keys.")
        print()
        print("=" * 80)
        print("TEMPLATE: Here's what your .env file should look like:")
        print("=" * 80)
        print()
        print(get_bundled_env_example())
        print()
        print("=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print()
        print("1. Create a new file named '.env' in the same directory as this executable")
        print("2. Copy the template above into your .env file")
        print("3. Replace the placeholder values with your actual API keys")
        print("4. Run this application again:")
        print(f"     {Path(sys.argv[0]).name} --env .env")
        print()
        print("=" * 80)

        return False

    return True


def main():
    """Simple client that uses llm_selector."""

    # Parse command-line arguments
    args = parse_arguments()

    # Validate that .env file exists
    if not validate_env_file(args.env):
        sys.exit(1)

    print("=" * 60)
    print("Sample Client - LLM Selector Demo")
    print("=" * 60)
    print(f"Using .env file: {Path(args.env).absolute()}")
    print("=" * 60)
    print()

    # Initialize the selector with the provided .env path
    try:
        selector = LLMSelector(dotenv_path=args.env)
    except Exception as e:
        print(f"Error initializing LLMSelector: {str(e)}")
        print()
        print("Please check that your .env file contains valid API keys.")
        sys.exit(1)

    # Example 1: Get a provider for GPT-4.1
    print("Example 1: Request provider for gpt-4.1")
    print("-" * 60)
    result = selector.suggest_provider("gpt-4.1")

    if result["success"]:
        provider = result["provider"]
        print(f"✓ Selected provider: {provider['model_id']}")
    else:
        print(f"✗ Error: {result['reason']}")
    print()

    # Example 2: Simulate failure and retry
    print("Example 2: Simulate failure and retry")
    print("-" * 60)

    result1 = selector.suggest_provider("gpt-4.1")
    if result1["success"]:
        print(f"✓ Initial provider: {result1['provider']['model_id']}")

        # Simulate a 429 rate limit error
        print("  Simulating 429 rate limit error...")
        result2 = selector.retry_suggestion("gpt-4.1", status_code=429)

        if result2["success"]:
            print(f"✓ Retry provider: {result2['provider']['model_id']}")
        else:
            print(f"✗ Retry failed: {result2['reason']}")
    print()

    # Example 3: Inspect memory state
    print("Example 3: Inspect memory state")
    print("-" * 60)
    state = selector.get_memory_state()
    print(f"Total failure records: {len(state['failure_records'])}")
    print(f"Last suggested providers: {len(state['last_suggested'])}")

    if state['failure_records']:
        print("\nFailed providers:")
        for model_id, record in state['failure_records'].items():
            print(f"  • {model_id}: HTTP {record['status_code']}")
    print()

    # Example 4: Try Claude Sonnet 4.5
    print("Example 4: Request Claude Sonnet 4.5")
    print("-" * 60)
    result = selector.suggest_provider("claude-sonnet-4-5")

    if result["success"]:
        provider = result["provider"]
        print(f"✓ Provider: {provider['model_id']}")
        print(f"  Model: {provider['model']}")
        print(f"  Region: {provider.get('aws_bedrock', {}).get('aws_region_name', 'N/A')}")
    else:
        print(f"✗ Error: {result['reason']}")
    print()

    # Example 5: Ad-hoc provider override with suggest_provider_by_id
    print("Example 5: Ad-hoc provider override (suggest_provider_by_id)")
    print("-" * 60)
    print("  Use case: bypass provider selection and target a specific provider directly")
    print("  (e.g. when a provider had content guardrail issues on the last request)")
    result = selector.suggest_provider_by_id("openai-gpt-4.1")

    if result["success"]:
        provider = result["provider"]
        print(f"✓ Provider: {provider['model_id']}")
        print(f"  Model: {provider['model']}")
    else:
        print(f"✗ Error: {result['reason']}")
    print()

    # Example 6: Reset memory store and verify state is cleared
    print("Example 6: Reset memory store")
    print("-" * 60)
    state_before = selector.get_memory_state()
    print(f"Before reset — failure records: {len(state_before['failure_records'])}, "
          f"last suggested: {len(state_before['last_suggested'])}")

    selector.reset_memory_store()

    state_after = selector.get_memory_state()
    print(f"After reset  — failure records: {len(state_after['failure_records'])}, "
          f"last suggested: {len(state_after['last_suggested'])}")
    print("✓ Memory store cleared")
    print()

    # Example 7: Round-robin with 4 real API calls (one per gpt-4.1 provider)
    print("Example 7: Round-robin chat completions (gpt-4.1, 4 iterations)")
    print("-" * 60)
    eq_selector = LLMSelector(dotenv_path=args.env, as_equal_as_possible=True)

    for idx in range(1, 5):
        print(f"  Iteration {idx}:")
        result = eq_selector.suggest_provider("gpt-4.1")
        if result["success"]:
            selected_provider = result["provider"]
            base_url = selected_provider["api_base"]
            api_key = selected_provider["api_key"]
            api_version = selected_provider.get("api_version", "")

            print(f"  Provider: {selected_provider['model_id']}")

            is_azure_client = "azure" in base_url
            client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=base_url) if is_azure_client else OpenAI(base_url=base_url, api_key=api_key)
            try:
                completion = client.chat.completions.create(
                    model=selected_provider["model"],
                    messages=[
                        {"role": "user", "content": "Hello! Can you tell me a fun fact about space?"}
                    ],
                )
                print("  Response from Azure:" if is_azure_client else "  Response from OpenAI:")
                print(f"  {completion.choices[0].message.content}")

            except APITimeoutError as e:
                print(f"  ✗ Timeout error: {str(e)}")
                retry_result = eq_selector.retry_suggestion("gpt-4.1", status_code=408)
                if retry_result["success"]:
                    print(f"  Retry suggested: {retry_result['provider']['model_id']}")
                else:
                    print(f"  No retry available: {retry_result['reason']}")

            except APIConnectionError as e:
                print(f"  ✗ Connection error: {str(e)}")
                retry_result = eq_selector.retry_suggestion("gpt-4.1", status_code=500)
                if retry_result["success"]:
                    print(f"  Retry suggested: {retry_result['provider']['model_id']}")
                else:
                    print(f"  No retry available: {retry_result['reason']}")

            except APIError as e:
                print(f"  ✗ API error: {str(e)}")
                status_code = getattr(e, 'status_code', 500)
                retry_result = eq_selector.retry_suggestion("gpt-4.1", status_code=status_code)
                if retry_result["success"]:
                    print(f"  Retry suggested: {retry_result['provider']['model_id']}")
                else:
                    print(f"  No retry available: {retry_result['reason']}")

            except Exception as e:
                print(f"  ✗ Unexpected error: {str(e)}")
                retry_result = eq_selector.retry_suggestion("gpt-4.1", status_code=500)
                if retry_result["success"]:
                    print(f"  Retry suggested: {retry_result['provider']['model_id']}")
                else:
                    print(f"  No retry available: {retry_result['reason']}")
        else:
            print(f"  ✗ No provider available: {result['reason']}")

        print()

    print("=" * 60)
    print("Sample client completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
