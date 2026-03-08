# LLM Selector

Intelligently route LLM requests across multiple providers with automatic retry logic and cooldown tracking for rate-limited or failed providers.

## Documentation

- **[Workflow Diagrams](WORKFLOW_DIAGRAMS.md)** - Comprehensive workflow diagrams with architecture, selection strategies, and detailed algorithm flowcharts
- **[Behavior Comparison](BEHAVIOR_COMPARISON.md)** - Detailed comparison of random vs round-robin selection strategies

## Features

- **Multi-Provider Support**: Seamlessly route requests across OpenAI, Azure OpenAI, AWS Bedrock, and custom endpoints
- **Automatic Retry Logic**: Intelligent retry mechanism that tracks failures and suggests alternative providers
- **Cooldown Tracking**: 60-second cooldown period prevents hammering recently failed providers
- **Selection Strategies**: Choose between random selection (default) or round-robin for equal distribution
- **Environment Variable Management**: Secure API key management using python-dotenv
- **Memory-Efficient**: In-memory failure tracking with manual reset capability

## Installation

Using uv (recommended):

```bash
cd libs/llm-selector
uv sync
```

Or with pip:

```bash
pip install -e .
```

For development with test dependencies:

```bash
uv sync --dev
```

## Quick Start

```python
from llm_selector import LLMSelector

# Initialize with .env path (random selection by default)
selector = LLMSelector(dotenv_path=".env")

# Or enable round-robin for equal distribution
# selector = LLMSelector(dotenv_path=".env", as_equal_as_possible=True)

# Get initial provider suggestion
result = selector.suggest_provider("gpt-4.1")

if result["success"]:
    provider = result["provider"]
    print(f"Using provider: {provider['model_id']}")
    print(f"API Key: {provider['api_key']}")
    print(f"API Base: {provider['api_base']}")

    # Make your LLM API call here...
    # If it fails with 429 or 5xx, use retry:

    # response = make_api_call(provider)
    # if response.status_code in [429, 500, 502, 503]:
    #     retry_result = selector.retry_suggestion("gpt-4.1", response.status_code)
else:
    print(f"Error: {result['reason']}")
```

## Configuration

### Environment Variables

Create a `.env` file in your project root (see `.env.example`):

```bash
# OpenAI
OPENAI_APIKEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1

# Azure OpenAI (multiple regions)
AZURE_OPENAI_APIKEY_AUEAST=...
AZURE_OPENAI_API_BASE_AUEAST=https://[region].openai.azure.com/openai/v1

AZURE_OPENAI_APIKEY_NORTHCENTRALUS=...
AZURE_OPENAI_API_BASE_NORTHCENTRALUS=https://[region].openai.azure.com/openai/v1

AZURE_OPENAI_APIKEY_SOUTHCENTRALUS=...
AZURE_OPENAI_API_BASE_SOUTHCENTRALUS=https://[region].openai.azure.com/openai/v1
```

AWS Bedrock (`claude-sonnet-4-5`) uses standard AWS credential methods (environment variables, `~/.aws/credentials`, or IAM roles) — no API key in `.env`.

### Supported Models

The library comes pre-configured with the following models:

- `gpt-5.1` - OpenAI GPT-5.1
- `gpt-5.2` - OpenAI GPT-5.2
- `gpt-4.1` - OpenAI GPT-4.1 + 3 Azure regions
- `claude-sonnet-4-5` - AWS Bedrock Claude Sonnet 4.5

## API Reference

### LLMSelector

The main class for provider selection and retry logic.

#### `__init__(dotenv_path: str = ".env", as_equal_as_possible: bool = False)`

Initialize the selector with environment variables.

**Parameters:**
- `dotenv_path` (str): Path to .env file. Default: ".env"
- `as_equal_as_possible` (bool): If True, use round-robin selection for equal distribution. If False (default), use random selection.

#### `suggest_provider(model_name: str) -> dict`

Get an initial provider suggestion for a model.

**Parameters:**
- `model_name` (str): Name of the model (e.g., "gpt-4.1")

**Returns:**
- Success: `{"success": True, "provider": {...}}`
- Error: `{"success": False, "reason": "..."}`

The `provider` dict contains different fields depending on provider type:

**OpenAI / Azure OpenAI:**
| Field | Description |
|-------|-------------|
| `model_id` | Unique provider identifier (e.g. `"azure-aueast-gpt-4.1"`) |
| `model` | Model name string |
| `api_base` | Resolved API endpoint URL |
| `api_key` | Resolved API key |
| `api_version` | Azure API version (Azure only, e.g. `"2024-02-15-preview"`) |

**AWS Bedrock:**
| Field | Description |
|-------|-------------|
| `model_id` | Unique provider identifier (e.g. `"bedrock-claude-sonnet-4-5"`) |
| `model` | Full Bedrock model path |
| `aws_bedrock` | Dict with `aws_region_name` and `anthropic_beta` |

**Example:**
```python
result = selector.suggest_provider("gpt-4.1")
if result["success"]:
    provider = result["provider"]
    # Use provider["api_key"], provider["api_base"], etc.
```

#### `suggest_provider_by_id(model_id: str) -> dict`

Suggest a specific provider directly by its `model_id`, bypassing the normal selection algorithm.

**Parameters:**
- `model_id` (str): Unique provider identifier (e.g. `"openai-gpt-4.1"`)

**Returns:**
- Success: `{"success": True, "provider": {...}}`
- Error: `{"success": False, "reason": "..."}`

**Notes:**
- `last_suggested` is **not** updated — round-robin state is fully preserved.
- No failure is recorded.
- If the provider is in cooldown, returns `success: False` with the remaining wait time.

**Example — Azure guardrail workaround:**
```python
# Normal flow — may return an Azure provider
result = selector.suggest_provider("gpt-4.1")
# result["provider"]["model_id"] might be "azure-aueast-gpt-4.1"
# If Azure rejects with a content guardrail error, bypass directly to OpenAI:

override = selector.suggest_provider_by_id("openai-gpt-4.1")
if override["success"]:
    provider = override["provider"]
    # retry your request with provider
```

#### `retry_suggestion(model_name: str, status_code: int) -> dict`

Retry provider suggestion after a failure.

**Parameters:**
- `model_name` (str): Name of the model
- `status_code` (int): HTTP status code from failed request

**Returns:**
- Success: `{"success": True, "provider": {...}}`
- Error: `{"success": False, "reason": "..."}`

**Example:**
```python
# After a failed request
retry = selector.retry_suggestion("gpt-4.1", status_code=429)
if retry["success"]:
    provider = retry["provider"]
    # Try again with new provider
```

#### `get_memory_state() -> dict`

Get current memory store state for debugging.

**Returns:**
```python
{
    "failure_records": {
        "provider-id": {
            "model_id": "provider-id",
            "status_code": 429,
            "recorded_at": "2024-01-15T10:30:45"
        }
    },
    "last_suggested": {
        "gpt-4.1": "azure-aueast-gpt-4.1"
    }
}
```

#### `reset_memory_store()`

Clear all failure records, last suggested tracking, and round-robin state.

**Use Cases:**
- Testing
- Preventing memory leaks in long-running processes
- Manual override of cooldown periods

## Advanced Usage

### Checking Memory State

```python
# Inspect current state
state = selector.get_memory_state()
print(f"Failed providers: {len(state['failure_records'])}")
print(f"Last suggestions: {state['last_suggested']}")
```

### Manual Reset

```python
# Clear all failure records
selector.reset_memory_store()

# Now all providers are available again
result = selector.suggest_provider("gpt-4.1")
```

### Handling All Providers Busy

```python
result = selector.suggest_provider("gpt-4.1")

if not result["success"]:
    if "all providers are busy" in result["reason"]:
        # Extract wait time from reason
        # Format: "all providers are busy, .... please wait for Xs"
        print(f"All providers busy: {result['reason']}")
        # Implement exponential backoff or inform user
```

### Custom Retry Logic

```python
import time

def make_request_with_retry(selector, model_name, max_retries=3):
    """Make LLM request with automatic retry."""

    # Get initial provider
    result = selector.suggest_provider(model_name)

    for attempt in range(max_retries):
        if not result["success"]:
            print(f"No provider available: {result['reason']}")
            return None

        provider = result["provider"]

        # Make your API call here
        # response = your_api_call(provider)

        # Simulate API call
        status_code = 429  # Simulate rate limit

        if status_code == 200:
            return "Success!"

        # Retry with different provider
        if attempt < max_retries - 1:
            result = selector.retry_suggestion(model_name, status_code)
            time.sleep(1)  # Brief delay between retries

    return None
```

## Testing

Run all tests:

```bash
uv run pytest tests/ -v
```

Run specific test file:

```bash
uv run pytest tests/test_selector.py -v
```

Run with coverage:

```bash
uv run pytest tests/ --cov=llm_selector --cov-report=html
```

## Deployment

### Bump the patch version

From the `libs/` directory:

```bash
./bump-version.sh
```

This updates `version` in `pyproject.toml` (e.g. `0.1.0` → `0.1.1`) and re-locks the project.

### Build the package

```bash
./build.sh
```

Produces a source distribution (`.tar.gz`) and wheel (`.whl`) in `dist/`.

## Design Decisions

### In-Memory Store

The library uses an in-memory store for failure tracking, which means:
- ✅ Simple and fast
- ✅ No external dependencies
- ✅ Suitable for single-process usage
- ⚠️ State resets on process restart
- ⚠️ Not shared across multiple processes

For distributed systems, consider implementing a custom store using Redis or similar.

### 60-Second Cooldown

Providers are marked unavailable for 60 seconds after a failure. This prevents:
- Hammering rate-limited providers
- Cascading failures
- Wasting API quota on failing providers

The cooldown only updates if a new failure occurs >60s after the previous one.

### Selection Strategies

The library supports two selection strategies:

**Random Selection (default):**
- Uses `random.choice()` to select from available providers
- Simple and effective load distribution
- Good for unpredictable request patterns

**Round-Robin Selection:**
- Enable with `as_equal_as_possible=True`
- Ensures equal distribution across providers
- Maintains sequence even when providers fail
- Best for predictable, fair load balancing

See [Workflow Diagrams](WORKFLOW_DIAGRAMS.md) for detailed explanations and visual flowcharts of both strategies.

## Troubleshooting

### "Warning: Environment variable X not found"

**Cause:** API key environment variable is not set.

**Solution:**
1. Check your `.env` file exists
2. Verify the variable name matches exactly
3. Ensure `.env` is in the correct location
4. Try restarting your application

### "all providers are busy"

**Cause:** All providers for the model are in cooldown.

**Solution:**
1. Wait for the specified time (displayed in error message)
2. Check if you're hitting rate limits too frequently
3. Consider adding more provider regions
4. Implement exponential backoff in your retry logic

### Providers not rotating

**Cause:** Random selection might choose the same provider multiple times.

**Solution:**
- This is normal behavior with random selection
- Over many requests, distribution will be approximately even
- For deterministic rotation, use round-robin: `LLMSelector(as_equal_as_possible=True)`

### Memory leak concerns

**Solution:**
- Call `reset_memory_store()` periodically in long-running processes
- Monitor memory usage with `get_memory_state()`
- Consider implementing automatic cleanup for old records

## Contributing

### Adding New Providers

Edit `src/llm_selector/config.py`:

```python
MODEL_MAPPINGS = {
    "your-model": [
        {
            "model_id": "provider-1-your-model",
            "model": "provider/your-model",
            "api_base": "https://api.example.com",
            "api_key": "YOUR_API_KEY_ENV_VAR"
        }
    ]
}
```

### Adding Tests

Create test files in `tests/` directory following the existing patterns.

## License

MIT License - see LICENSE file for details.

## Support

For issues, questions, or contributions, please open an issue on the project repository.
