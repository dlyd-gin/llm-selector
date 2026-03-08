# Building a Lightweight LLM Selector: A LiteLLM Proxy Alternative Without the Infrastructure

---

If you're routing production traffic through multiple LLM providers — OpenAI, Azure OpenAI, AWS Bedrock — you've probably looked at LiteLLM Proxy. It's a compelling pitch: one endpoint, unified keys, automatic fallback. But after running it for a while, the hidden costs start to show up. This post is about what I built instead.

---

## The Problem with Managed LLM Gateways

LiteLLM Proxy genuinely solves hard problems. Behind a single OpenAI-compatible URL, it can:

- **Load balance** across multiple providers and regions
- **Fall back** automatically when a provider returns 429 or 5xx
- **Unify API keys** so your application code never changes when you swap providers

That's valuable. But operating the proxy comes with its own overhead:

**Infrastructure.** The proxy is a separate service — typically running on ECS, EC2, or similar. That means containers to manage, health checks to configure, load balancers to set up, and deployment pipelines to maintain. For a small team, that's a meaningful ongoing cost.

**Dependency risk.** LiteLLM is a fast-moving open-source project. The changelog is long. The bug tracker is active. Every upgrade carries the risk of a subtle behavior change in the routing or retry logic you're depending on.

**Latency.** Every LLM request now hops through an intermediate service, even when everything is healthy. For high-throughput applications, that adds up.

I started thinking: the core logic isn't that complicated. Provider selection, failure tracking, cooldown, retry. What if it lived in the application process itself?

---

## Introducing LLM Selector

`llm-selector` is a small Python library that provides in-process LLM provider routing. No proxy, no extra service, no intermediate hop.

The same benefits you get from LiteLLM Proxy — multi-provider support, automatic retry, OpenAI-compatible provider configs — but as a library you import, not infrastructure you operate.

**Core features:**

- **Multi-provider support**: OpenAI, Azure OpenAI (multiple regions), AWS Bedrock
- **Automatic retry logic**: When a provider fails, the library records the failure and suggests an alternative
- **Cooldown tracking**: Failed providers are excluded for 60 seconds — no hammering a rate-limited endpoint
- **Two selection strategies**: Random (default) or round-robin for equal distribution
- **Environment variable management**: API keys live in `.env`, resolved at startup
- **In-memory state**: Simple and fast; swappable to Redis for distributed systems

**Supported models out of the box:**

| Model | Providers |
|-------|-----------|
| `gpt-4.1` | OpenAI + 3 Azure regions (AU East, North Central US, South Central US) |
| `gpt-5.1` / `gpt-5.2` | OpenAI |
| `claude-sonnet-4-5` | AWS Bedrock (us-west-2) |

---

## Architecture

The library has three components:

```
┌─────────────────────────────────────────────────────┐
│                   Your Application                  │
│                                                     │
│  result = selector.suggest_provider("gpt-4.1")      │
│  provider = result["provider"]                      │
│                                                     │
│  client = openai.OpenAI(                            │
│      api_key=provider["api_key"],                   │
│      base_url=provider["api_base"]                  │
│  )                                                  │
│  response = client.chat.completions.create(         │
│      model=provider["model"], messages=[...]        │
│  )                                                  │
│                                                     │
│  # On failure → selector.retry_suggestion(model, status_code)
└──────────────────────────┬──────────────────────────┘
                           │  suggest_provider()
                           │  retry_suggestion()
                           ▼
┌─────────────────────────────────────────────────────┐
│               LLMSelector (selector.py)        │
│                                                     │
│  • Validates model name                             │
│  • Filters available providers via MemoryStore      │
│  • Applies selection strategy (random / RR)         │
│  • Tracks last_suggested for retry                  │
│  • Tracks round_robin_last_used for sequencing      │
└───────────────┬─────────────────┬───────────────────┘
                │                 │
                ▼                 ▼
┌───────────────────┐   ┌─────────────────────────────┐
│  MemoryStore      │   │  config.py                  │
│  (memory_store.py)│   │                             │
│                   │   │  MODEL_MAPPINGS:            │
│  _store:          │   │  model_name →               │
│   model_id →      │   │  [provider_1, provider_2,   │
│   {timestamp,     │   │   provider_3, ...]          │
│    status_code}   │   │                             │
│                   │   │  Each provider has:         │
│  is_available()   │   │  model_id, model,           │
│  record_failure() │   │  api_base, api_key,         │
│  calculate_wait() │   │  api_version (Azure)        │
└───────────────────┘   └─────────────────────────────┘
```

**LLMSelector** is the main entry point. It holds the selection strategies, tracks state, and exposes the public API.

**MemoryStore** knows which providers are in cooldown. It stores a failure record (timestamp + status code) per provider ID. When `is_available()` is called, it checks whether 60 seconds have elapsed since the last failure.

**config.py** contains `MODEL_MAPPINGS` — a static dict that maps model names to provider lists. Each entry in the list is a provider config:

```python
MODEL_MAPPINGS = {
    "gpt-4.1": [
        {
            "model_id": "openai-gpt-4.1",
            "model": "gpt-4.1",
            "api_base": "OPENAI_API_BASE",      # env var name
            "api_key": "OPENAI_APIKEY"           # env var name
        },
        {
            "model_id": "azure-aueast-gpt-4.1",
            "model": "gpt-4.1",
            "api_base": "AZURE_OPENAI_API_BASE_AUEAST",
            "api_key": "AZURE_OPENAI_APIKEY_AUEAST",
            "api_version": "2024-02-15-preview"
        },
        # ... more Azure regions
    ],
}
```

The values for `api_base` and `api_key` are environment variable names. At initialization, `LLMSelector` resolves these against the loaded `.env` file, so the resolved config contains actual keys and URLs — never stored in code.

---

## The Workflow

### suggest_provider() — how a provider is selected

```
suggest_provider("gpt-4.1")
         │
         ▼
 Is "gpt-4.1" a known model?
         │
    No ──┼──► return {success: False, reason: "no provider available..."}
         │
    Yes  ▼
 Get all providers for model
 Filter out providers in cooldown (MemoryStore.is_available)
         │
 Any available?
         │
    No ──┼──► calculate_shortest_wait()
         │    return {success: False, reason: "all providers are busy, wait Xs"}
         │
    Yes  ▼
 Apply selection strategy
 ┌───────────────┬──────────────────────────┐
 │ random=True   │ as_equal_as_possible=True │
 │ random.choice │ round-robin by ID         │
 └───────┬───────┴────────────┬─────────────┘
         └─────────┬──────────┘
                   ▼
         Store in last_suggested[model_name]
                   │
                   ▼
         return {success: True, provider: {...}}
```

### retry_suggestion() — what happens on failure

```
retry_suggestion("gpt-4.1", status_code=429)
         │
         ▼
 Record failure in MemoryStore:
   last_suggested["gpt-4.1"] → provider_id
   store {timestamp: now, status_code: 429}
   cooldown starts (60 seconds)
         │
         ▼
 Same flow as suggest_provider()
 (failed provider is now filtered out)
         │
         ▼
 return {success: True, provider: <different provider>}
       OR
 return {success: False, reason: "all providers are busy, wait Xs"}
```

### The three scenarios

**Happy path:**
```
suggest_provider("gpt-4.1")  →  openai-gpt-4.1
API call  →  200 OK
Done.
```

**Failure path:**
```
suggest_provider("gpt-4.1")  →  azure-aueast-gpt-4.1
API call  →  429 Too Many Requests

retry_suggestion("gpt-4.1", 429)
  records azure-aueast-gpt-4.1 as failed (60s cooldown)
  →  openai-gpt-4.1 (next available)

API call  →  200 OK
Done.
```

**Worst case — all providers in cooldown:**
```
retry_suggestion("gpt-4.1", 429)
  all 4 providers now in cooldown
  →  {success: False, reason: "all providers are busy,
       4 provider(s) in cooldown: [...],
       please wait for 45s"}
```

The error message tells you exactly how long to wait. Your application can implement exponential backoff or surface this to the caller.

---

## Selection Strategies

### Random (default)

```python
selector = LLMSelector(dotenv_path=".env")
```

Uses `random.choice()` on the list of available providers. Simple and effective. Over many requests, distribution is approximately even. Good for unpredictable traffic or when you don't need strict fairness.

### Round-Robin (`as_equal_as_possible=True`)

```python
selector = LLMSelector(dotenv_path=".env", as_equal_as_possible=True)
```

Ensures equal distribution over time by cycling through providers in config order. The implementation is worth discussing, because the naive approach has a subtle bug.

**The index-based approach (broken):**

Most round-robin implementations store the current *index* and compute `index % len(available_providers)`. This breaks as soon as a provider enters cooldown:

| Step | Available | Stored Index | Index % len | Selected | Problem |
|------|-----------|-------------|-------------|----------|---------|
| 1 | [A, B, C, D] | 0 | 0 % 4 = 0 | A | OK |
| 2 | [A, B, C, D] | 1 | 1 % 4 = 1 | B | OK |
| 3 | [B, C, D] (A cooldown) | 2 | 2 % 3 = 2 | **D** | Skipped C |
| 4 | [B, C, D] | 0 | 0 % 3 = 0 | **B** | Jumped back |

Provider C was skipped entirely. The distribution is uneven, and the behavior depends on *when* the cooldown happens.

**The ID-based approach (correct):**

Instead of tracking a position index, track the ID of the last used provider. When selecting the next one, look up that ID's position in the *full* provider list (not the filtered one), then find the next available.

| Step | Available | Last Used | Next in Full List | Selected |
|------|-----------|-----------|-------------------|----------|
| 1 | [A, B, C, D] | — | A (first) | A |
| 2 | [A, B, C, D] | A | B | B |
| 3 | [B, C, D] (A cooldown) | B | C | **C** (correct) |
| 4 | [B, C, D] | C | D | D |
| 5 | [B, C, D] | D | A→skip, B (wrap) | **B** (correct wrap) |

The key insight: the reference list for sequencing is the *static config order*, not the dynamic available list. When a provider goes in or out of cooldown, the sequence doesn't shift — it just skips the unavailable entries.

The relevant code from `selector.py`:

```python
def _select_provider(self, model_name: str, available_providers: list) -> dict:
    if not self.as_equal_as_possible:
        return random.choice(available_providers)

    all_providers = self.resolved_mappings[model_name]  # full static list

    if model_name not in self.round_robin_last_used:
        selected = available_providers[0]
        self.round_robin_last_used[model_name] = selected["model_id"]
        return selected

    last_used_id = self.round_robin_last_used[model_name]
    last_position = next(
        (i for i, p in enumerate(all_providers) if p["model_id"] == last_used_id),
        None
    )

    available_ids = {p["model_id"] for p in available_providers}  # O(1) lookup

    for offset in range(1, len(all_providers) + 1):
        next_position = (last_position + offset) % len(all_providers)
        candidate = all_providers[next_position]
        if candidate["model_id"] in available_ids:
            self.round_robin_last_used[model_name] = candidate["model_id"]
            return candidate
```

**Real-world impact at scale:**

Over 100 requests with 4 providers:

| Strategy | Distribution |
|---------|-------------|
| Index-based round-robin | A=30, B=45, C=15, D=10 (depends on cooldown timing) |
| ID-based round-robin | A=25, B=25, C=25, D=25 (consistent) |

The performance cost is negligible: O(n) where n is typically 2–4 providers, all in-memory string comparisons. At 3000 req/s this adds under 0.01ms per request.

---

## How to Use It

### Installation

From a local path (install in your app's virtualenv):

```bash
pip install -e ./libs/llm-selector
# or with uv:
uv add ./libs/llm-selector
```

### Configure your .env

```bash
# OpenAI
OPENAI_APIKEY=sk-your-actual-key
OPENAI_API_BASE=https://api.openai.com/v1

# Azure OpenAI (multiple regions)
AZURE_OPENAI_APIKEY_AUEAST=your-azure-key
AZURE_OPENAI_API_BASE_AUEAST=https://[your-resource].openai.azure.com/openai/v1

AZURE_OPENAI_APIKEY_NORTHCENTRALUS=your-azure-key-2
AZURE_OPENAI_API_BASE_NORTHCENTRALUS=https://[your-resource].openai.azure.com/openai/v1
```

AWS Bedrock uses standard AWS credential methods (environment variables, `~/.aws/credentials`, or IAM roles) — no key needed in `.env`.

### Basic suggest + retry loop

```python
import requests
from llm_selector import LLMSelector

def make_llm_request(prompt: str, model: str = "gpt-4.1"):
    selector = LLMSelector(dotenv_path=".env")
    result = selector.suggest_provider(model)

    while result["success"]:
        provider = result["provider"]

        response = requests.post(
            f"{provider['api_base']}/chat/completions",
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": provider["model"],
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json()

        # Record failure, get next available provider
        result = selector.retry_suggestion(model, response.status_code)

    # All providers exhausted
    raise Exception(f"All providers failed: {result['reason']}")
```

### Ad-hoc override with suggest_provider_by_id()

Sometimes you need to bypass the selection logic entirely. For example, if an Azure region consistently rejects a specific request due to content guardrails, you can pin directly to OpenAI without disrupting the round-robin state for other requests:

```python
# Normal flow — may return Azure
result = selector.suggest_provider("gpt-4.1")
# result["provider"]["model_id"] == "azure-aueast-gpt-4.1"

# Azure rejects with content guardrail → bypass directly to OpenAI
override = selector.suggest_provider_by_id("openai-gpt-4.1")
if override["success"]:
    provider = override["provider"]
    # retry with this provider
```

`suggest_provider_by_id()` does not update `last_suggested` or `round_robin_last_used` — the normal rotation is fully preserved. It also respects cooldown: if the requested provider is in cooldown, it returns an error with the wait time.

### Debugging state

```python
state = selector.get_memory_state()
# {
#   "failure_records": {
#     "azure-aueast-gpt-4.1": {
#       "model_id": "azure-aueast-gpt-4.1",
#       "status_code": 429,
#       "recorded_at": "2025-03-05T10:30:45"
#     }
#   },
#   "last_suggested": {
#     "gpt-4.1": "azure-aueast-gpt-4.1"
#   }
# }

# Clear everything (useful after a bad run or in tests)
selector.reset_memory_store()
```

---

## Discussion Topics

### Topic A: When does a custom solution beat LiteLLM Proxy?

LiteLLM Proxy makes a lot of sense when you have many teams, many services, and want a central routing layer with a dashboard. You pay the infra cost once and get broad visibility.

But the value proposition inverts for:

- **Small teams with few services.** If you have one or two Python services, maintaining a separate proxy node is pure overhead. The library is a pip install.
- **Single-process applications.** A library embedded in your process can't fail independently. With a proxy, you have two services to keep healthy instead of one.
- **Strict dependency audits.** LiteLLM touches a lot of surface area — it supports dozens of providers, has a large transitive dependency tree, and moves fast. If your org audits every package version before deploying, a small focused library is easier to review and pin.
- **Wanting to own the routing logic.** When the retry behavior or cooldown tuning doesn't match your needs, you modify a Python file you control — no upstream PR, no version bump dance.

The tradeoff is real: LiteLLM Proxy has features this library doesn't (spend tracking, a web dashboard, broader provider coverage, streaming). The question is whether you need those things.

### Topic B: Why index-based round-robin is subtly broken

This is worth spending a moment on because the bug isn't obvious until you think about it carefully.

The standard round-robin implementation stores an index and uses modulo arithmetic:

```python
# Naive implementation
index = self.indices[model] % len(available_providers)
self.indices[model] = (index + 1) % len(available_providers)
return available_providers[index]
```

This works perfectly when the provider list is static. The problem is that `available_providers` changes as providers enter and exit cooldown.

Consider 4 providers [A, B, C, D] and index=2 stored:
- If all 4 are available: `2 % 4 = 2` → C. Correct.
- If A is in cooldown, list becomes [B, C, D]: `2 % 3 = 2` → D. **Skipped C.**
- Next call, index=3: `3 % 3 = 0` → B. **Jumped back.**

The index is a position in a *dynamic* list, so it drifts relative to the actual provider order as the list shrinks and grows. The result is uneven distribution that depends on the timing of failures rather than config order.

The fix is to track identity, not position. Store the ID of the last used provider. To find the next one:
1. Find the last used ID's position in the *full, static* list (from config).
2. Walk forward from that position (with wraparound), skipping providers in cooldown.

Now the reference is stable. When A goes into cooldown, the position of B, C, D in the full list doesn't change — the algorithm just skips A when it comes up in the cycle. The sequence is always: …C → D → (skip A) → B → C…, regardless of when the cooldown started.

This matters most when cooldowns are frequent — which is exactly when you need round-robin to be reliable.

---

## Summary

`llm-selector` is a ~350-line Python library that handles:

- Multi-provider routing across OpenAI, Azure OpenAI, and AWS Bedrock
- Automatic failure recording and cooldown tracking (60s)
- Two selection strategies: random and ID-based round-robin
- Ad-hoc provider override without disturbing routing state
- In-memory state with an easy path to distributed state via Redis

The core trade-off is straightforward: you get zero infra overhead and full control over routing logic, in exchange for the library being in-process (single-node state) and you being responsible for evolving it.

For teams running one or two Python services against a handful of LLM providers, this is often a better fit than a managed proxy. For larger, multi-service architectures where a central routing layer makes sense, LiteLLM Proxy is still a reasonable choice.

The interesting design problem in building something like this isn't the retry logic — it's the round-robin correctness. Index-based tracking breaks under dynamic availability. ID-based tracking with a static reference list is the fix, and it's O(n) with n typically 2–4.

---

*The full library code and sample client are in the repo. The `BEHAVIOR_COMPARISON.md` file has a detailed walkthrough of the round-robin scenarios with step tables.*
