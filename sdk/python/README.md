# CacheMind Python Client SDK

Official Python Client SDK for **CacheMind** — Safe, Measurable Semantic & Exact Caching Gateway for LLMs.

## Installation

```bash
pip install cachemind
```

## Quickstart

### 1. Synchronous Client (Drop-in OpenAI Compatible)

```python
from cachemind import CacheMindClient

client = CacheMindClient(
    api_key="cm_live_development_test_key_000000000000000000000000",
    base_url="http://localhost:8000"
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "What is semantic caching?"}
    ],
    tags=["env:prod", "v1"],
    namespace="kb_support"
)

print(response.choices[0].message.content)

# Inspect Cache Telemetry
print(f"Cache Status: {response.cachemind.status}")  # EXACT_HIT, SEMANTIC_HIT, CACHE_MISS
print(f"Similarity Score: {response.cachemind.similarity_score}")
print(f"Tokens Saved: {response.cachemind.tokens_saved}")
print(f"Cost Saved (USD): ${response.cachemind.cost_saved_usd}")
print(f"Roundtrip Latency: {response.cachemind.latency_ms}ms")
```

### 2. Asynchronous Client (Async / Await)

```python
import asyncio
from cachemind import AsyncCacheMindClient

async def main():
    async with AsyncCacheMindClient(
        api_key="cm_live_...",
        base_url="http://localhost:8000"
    ) as client:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello world!"}]
        )
        print(response.cachemind.status)

asyncio.run(main())
```

### 3. Cache Lifecycle & Invalidation

```python
# Granular Cache Invalidation
client.cache.purge(
    tenant_id="tenant_default",
    model="gpt-4o-mini",
    tags=["env:prod"]
)

# Pre-Warming / Cache Seeding
client.cache.warm(
    tenant_id="tenant_default",
    project_id="proj_default",
    items=[
        {
            "prompt": "What is CacheMind?",
            "completion": "CacheMind is an enterprise caching gateway.",
            "model": "gpt-4o-mini"
        }
    ]
)
```
