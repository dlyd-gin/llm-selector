# Sample Client for LLM Selector

This is a sample client demonstrating how to install and use the `llm_selector` package from a local directory.

## Installation

### Option 1: Using uv (recommended)

```bash
cd sample-client
uv sync
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

This will automatically create a virtual environment and install all dependencies including the local `llm-selector` package.

### Option 2: Using pip with requirements.txt

```bash
cd sample-client
pip install -r requirements.txt
```

### Option 3: Direct pip install from local path

```bash
# From the project root
pip install -e ./libs/llm-selector

# Or using the environment variable (if CLAUDE_PROJ_DIR is set)
pip install -e "$CLAUDE_PROJ_DIR/libs/llm-selector"
```

## Running the Sample Client

After installation:

```bash
python client.py --env .env
# or
python main.py --env .env
```

## What the Sample Client Demonstrates

| Example | Feature |
|---------|---------|
| 1 | `suggest_provider("gpt-4.1")` — basic provider selection |
| 2 | `retry_suggestion("gpt-4.1", 429)` — failure recording and retry with alternative provider |
| 3 | `get_memory_state()` — inspect failure records for debugging |
| 4 | `suggest_provider("claude-sonnet-4-5")` — multi-model support |
| 5 | `suggest_provider_by_id("openai-gpt-4.1")` — ad-hoc provider override (bypass selection logic) |
| 6 | `reset_memory_store()` — reset all failure records and last-suggested state |
| 7 | Round-robin chat completions — 4 real API calls with per-exception retry handling |

## Full API Reference

All methods on `LLMSelector`:

| Method | Description |
|--------|-------------|
| `suggest_provider(model_name)` | Select an available provider for the given model (random or round-robin) |
| `suggest_provider_by_id(model_id)` | Select a specific provider directly by its `model_id`, bypassing selection logic |
| `retry_suggestion(model_name, status_code)` | Record the last provider as failed and suggest an alternative |
| `get_memory_state()` | Return current failure records and last-suggested providers for debugging |
| `reset_memory_store()` | Clear all failure records and selection state |

## Environment Variables

Create a `.env` file with your API keys:

```bash
# OpenAI
OPENAI_APIKEY=sk-your-actual-key

# Azure OpenAI
AZURE_OPENAI_APIKEY_AUEAST=your-azure-key
AZURE_OPENAI_APIKEY_NORTHCENTRALUS=your-azure-key-2
AZURE_OPENAI_APIKEY_SOUTHCENTRALUS=your-azure-key-3
```

Then initialize with:

```python
selector = LLMSelector(dotenv_path=".env")
```

## Real-World Integration Example

```python
import requests
from llm_selector import LLMSelector

def make_llm_request(prompt: str, model: str = "gpt-4.1"):
    """Make LLM request with automatic provider failover."""
    selector = LLMSelector()

    # Get initial provider
    result = selector.suggest_provider(model)

    while result["success"]:
        provider = result["provider"]

        # Make API call
        try:
            response = requests.post(
                f"{provider['api_base']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {provider['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": provider['model'],
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )

            if response.status_code == 200:
                return response.json()

            # If failed, retry with different provider
            result = selector.retry_suggestion(model, response.status_code)

        except requests.RequestException as e:
            print(f"Request error: {e}")
            result = selector.retry_suggestion(model, status_code=500)

    # All providers failed
    raise Exception(f"All providers failed: {result['reason']}")
```

## Troubleshooting

### Import Error

If you see `ModuleNotFoundError: No module named 'llm_selector'`:

1. Make sure you've installed the package: `pip install -r requirements.txt`
2. Check that you're in the correct virtual environment
3. Verify the installation: `pip list | grep llm-selector`

### Environment Variable Warnings

If you see warnings about missing environment variables:
- Create a `.env` file based on `.env.example` and populate with your API keys
- Warnings for unused providers (e.g. Azure regions you haven't set up) can be ignored

## Next Steps

- Integrate into your application
- Add your own error handling logic
- Implement custom retry strategies
- Configure additional providers in `llm_selector/config.py`
