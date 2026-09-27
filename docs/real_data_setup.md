# CacheMind: Production Real-Data Setup & Deployment Guide

This guide outlines how to transition **CacheMind** from test doubles and local mocks to real upstream LLM providers, persistent production databases, distributed Redis caching, and live vector stores.

---

## 1. Quick Start with Real Providers

To connect CacheMind to real LLM APIs, create a `.env` file in the project root by copying `.env.example`:

```bash
cp .env.example .env
```

### Upstream LLM Configuration
Set your actual API keys in `.env`:

```ini
# Upstream OpenAI (e.g. gpt-4o, gpt-4o-mini, o1)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Upstream Anthropic (e.g. claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1

# Local or Remote Ollama (e.g. llama3, mistral, deepseek-r1)
OLLAMA_BASE_URL=http://localhost:11434
```

> **Dynamic Provider Routing**:
> When a client makes a request to `/v1/chat/completions`:
> - If `model` starts with `gpt-`, `o1`, or `o3` $\rightarrow$ routes to **OpenAIProvider** using `OPENAI_API_KEY`.
> - If `model` starts with `claude-` $\rightarrow$ routes to **AnthropicProvider** using `ANTHROPIC_API_KEY` (translating schemas bidirectionally).
> - If `model` starts with `llama`, `mistral`, `deepseek`, `phi`, etc. $\rightarrow$ routes to **OllamaProvider**.
> - If no API keys are provided in the environment, the gateway gracefully falls back to deterministic **MockProvider** test doubles.

---

## 2. Relational Database Setup (PostgreSQL)

For multi-node production deployment, switch from SQLite to PostgreSQL:

```ini
# .env
DATABASE_URL=postgresql+asyncpg://cachemind_user:your_password@localhost:5432/cachemind_db
```

### Apply Database Schema:
```bash
# Initialize tables using SQLAlchemy async engine
python -c "import asyncio; from backend.db.session import init_db; asyncio.run(init_db())"
```

---

## 3. Distributed L1 Exact Caching (Redis)

To enable multi-instance distributed exact caching:

```ini
# .env
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
REDIS_SOCKET_TIMEOUT=2.0
DEFAULT_CACHE_TTL_SECONDS=86400
```

CacheMind automatically uses Redis connection pooling with sliding TTL expiration and fail-open resilience (if Redis goes down, traffic transparently continues upstream).

---

## 4. Launching the CacheMind Gateway

Start the production gateway with Uvicorn:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 5. Verifying Live Traffic via OpenAI SDK

Point any standard OpenAI SDK client directly to CacheMind:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="cm_live_development_test_key_000000000000000000000000",
)

# 1. Test OpenAI upstream
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
)
print("OpenAI Upstream Response:", response.choices[0].message.content)

# 2. Test Anthropic upstream via OpenAI SDK format (auto-translated)
response_claude = client.chat.completions.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Write a haiku about caching."}],
)
print("Claude Response:", response_claude.choices[0].message.content)

# 3. Test exact L1 Cache Hit (Zero upstream cost, <1ms latency)
cached_response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
)
print("Cached Response (L1 Cache Hit!):", cached_response.choices[0].message.content)
```
