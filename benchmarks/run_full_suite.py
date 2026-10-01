#!/usr/bin/env python3
"""
CacheMind Full Empirical Benchmark Suite Runner.

Executes:
1. Exact Cache Hit Benchmark (1000 requests) @ concurrency 1, 10, 50, 100
2. Semantic Cache Hit Benchmark (1000 requests) @ concurrency 1, 10, 50, 100
3. Cache Miss Benchmark (1000 requests) @ concurrency 1, 10, 50, 100
4. Mixed Workload Benchmark (1000 requests) @ concurrency 1, 10, 50, 100
5. Customer Support 1000 Workload @ concurrency 10, 50, 100
6. Single-Flight Coalescing Concurrency Proof @ concurrency 10, 50, 100
7. Health Check Probes (/health/live, /health/ready)

Outputs structured JSON artifacts to benchmarks/results/
"""

import asyncio
import hashlib
import json
import logging
import os
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Setup project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings
from backend.app.main import app
from backend.auth.keys import hash_api_key
from backend.caching.factory import set_cache_backend
from backend.caching.memory import InMemoryExactCache
from backend.db.models import APIKey, Base, Project, Tenant
from backend.db.session import set_engine
from backend.guardrails.arbiter import GuardrailArbiter
from backend.guardrails.volatility import VolatilityEngine
from backend.guardrails.factory import set_guardrail_arbiter, set_volatility_engine
from backend.providers.factory import set_provider
from backend.providers.mock_provider import MockProvider
from backend.providers.registry import ProviderRegistry, set_provider_registry
from backend.ratelimit.limiter import RateLimiter, set_rate_limiter
from backend.resilience.circuit_breaker import get_circuit_breaker_registry
from backend.routing.engine import RoutingEngine, set_routing_engine
from backend.semantic.embedding import EmbeddingEngine
from backend.semantic.factory import SemanticCacheFactory
from backend.semantic.vector_index import VectorIndex

from benchmarks.benchmark_gateway import (
    BenchmarkSummary,
    RequestRecord,
    calculate_stats,
    get_git_metadata,
    get_hardware_environment,
    send_benchmark_request,
)
from benchmarks.load.test_single_flight_coalescing import run_coalescing_proof

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_runner")


async def setup_benchmark_environment(use_mock_upstream_delay: bool = False, delay_seconds: float = 0.035):
    """Initializes in-memory test database, test tenant/project/API key, and providers."""
    settings.ENVIRONMENT = "test"
    settings.ALLOW_MOCK_PROVIDERS = True
    settings.ALLOW_MOCK_EMBEDDINGS = False  # Real FastEmbed embeddings for accurate semantic benchmarks

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    set_engine(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed Tenant, Project, and API key
    test_key = "cm_live_development_test_key_000000000000000000000000"
    prefix = test_key[:8]
    key_hash = hash_api_key(test_key)

    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        t = Tenant(id="test_tenant_benchmark", name="Benchmark Tenant")
        p = Project(id="test_project_benchmark", tenant_id="test_tenant_benchmark", name="Benchmark Project")
        k = APIKey(
            id="test_key_benchmark",
            project_id="test_project_benchmark",
            key_prefix=prefix,
            key_hash=key_hash,
            name="Benchmark Key",
            role="admin",
            is_active=True,
        )
        session.add(t)
        session.add(p)
        session.add(k)
        await session.commit()

    # Reset singletons
    mem_cache = InMemoryExactCache()
    mock_prov = MockProvider(simulated_latency_ms=(delay_seconds * 1000.0) if use_mock_upstream_delay else 0.0)
    set_cache_backend(mem_cache)

    reg = ProviderRegistry()
    reg.register("mock", mock_prov)
    reg.register("openai", mock_prov)
    reg.register("anthropic", mock_prov)
    reg.register("ollama", mock_prov)
    set_provider_registry(reg)
    set_provider(mock_prov)
    set_routing_engine(RoutingEngine(provider_registry=reg))

    embedding_engine = EmbeddingEngine()
    vec_index = VectorIndex()
    arbiter = GuardrailArbiter()
    volatility = VolatilityEngine()

    SemanticCacheFactory.set_embedding_engine(embedding_engine)
    SemanticCacheFactory.set_vector_index(vec_index)
    SemanticCacheFactory.set_arbiter(arbiter)
    SemanticCacheFactory.set_volatility_engine(volatility)
    set_guardrail_arbiter(arbiter)
    set_volatility_engine(volatility)

    # High capacity rate limiter for benchmarks
    settings.DEFAULT_RPM_LIMIT = 1_000_000
    settings.DEFAULT_TPM_LIMIT = 50_000_000
    limiter = RateLimiter()
    set_rate_limiter(limiter)
    get_circuit_breaker_registry().reset_all()

    return test_key


async def run_scenario(
    client: AsyncClient,
    api_key: str,
    workload_items: List[Dict[str, Any]],
    concurrency: int,
    total_requests: int,
    warmup_count: int = 5,
    scenario_name: str = "Scenario",
) -> Tuple[BenchmarkSummary, List[RequestRecord]]:
    """Runs a concurrent benchmark scenario."""
    # Warmup
    for i in range(min(warmup_count, len(workload_items))):
        await send_benchmark_request(
            client=client,
            base_url="http://benchmark",
            api_key=api_key,
            payload=workload_items[i % len(workload_items)],
            req_index=-1,
            is_cold_start=False,
        )

    semaphore = asyncio.Semaphore(concurrency)
    records: List[RequestRecord] = []

    async def worker(idx: int, payload: Dict[str, Any]) -> RequestRecord:
        async with semaphore:
            return await send_benchmark_request(
                client=client,
                base_url="http://benchmark",
                api_key=api_key,
                payload=payload,
                req_index=idx,
                is_cold_start=False,
            )

    tasks = []
    t_start = time.perf_counter()
    for idx in range(total_requests):
        payload = workload_items[idx % len(workload_items)]
        tasks.append(asyncio.create_task(worker(idx, payload)))

    records = await asyncio.gather(*tasks)
    duration = time.perf_counter() - t_start

    successful = [r for r in records if r.status_code == 200]
    failed = [r for r in records if r.status_code != 200]

    exact_hits = [r for r in successful if r.cache_status == "EXACT_HIT"]
    semantic_hits = [r for r in successful if r.cache_status == "L2_HIT"]
    misses = [r for r in successful if r.cache_status in ("MISS", "ERROR")]

    exact_hit_rate = (len(exact_hits) / len(successful) * 100.0) if successful else 0.0
    semantic_hit_rate = (len(semantic_hits) / len(successful) * 100.0) if successful else 0.0
    overall_hit_rate = ((len(exact_hits) + len(semantic_hits)) / len(successful) * 100.0) if successful else 0.0
    throughput = len(successful) / duration if duration > 0 else 0.0

    client_lats = [r.client_latency_ms for r in successful]
    exact_lats = [r.gateway_latency_ms for r in exact_hits if r.gateway_latency_ms is not None]
    semantic_lats = [r.gateway_latency_ms for r in semantic_hits if r.gateway_latency_ms is not None]
    miss_lats = [r.gateway_latency_ms for r in misses if r.gateway_latency_ms is not None]
    lookup_lats = [r.lookup_latency_ms for r in successful if r.lookup_latency_ms is not None]

    summary = BenchmarkSummary(
        total_requests=len(records),
        successful_requests=len(successful),
        failed_requests=len(failed),
        duration_seconds=round(duration, 3),
        throughput_rps=round(throughput, 2),
        exact_hit_count=len(exact_hits),
        semantic_hit_count=len(semantic_hits),
        miss_count=len(misses),
        exact_hit_rate_pct=round(exact_hit_rate, 2),
        semantic_hit_rate_pct=round(semantic_hit_rate, 2),
        overall_hit_rate_pct=round(overall_hit_rate, 2),
        cold_start_latency_ms=None,
        client_latency_stats=calculate_stats(client_lats),
        exact_hit_latency_stats=calculate_stats(exact_lats),
        semantic_hit_latency_stats=calculate_stats(semantic_lats),
        miss_latency_stats=calculate_stats(miss_lats),
        lookup_latency_stats=calculate_stats(lookup_lats),
    )

    return summary, records


async def main_benchmark():
    print("=" * 80)
    print(" 🚀 CACHEMIND EMPIRICAL BENCHMARK SUITE — v0.1 PUBLIC BETA EVIDENCE")
    print("=" * 80)

    test_key = await setup_benchmark_environment(use_mock_upstream_delay=True, delay_seconds=0.035)

    transport = ASGITransport(app=app)
    limits = httpx.Limits(max_keepalive_connections=200, max_connections=400)
    client = AsyncClient(transport=transport, base_url="http://benchmark", limits=limits, timeout=60.0)

    # 1. Health Probe Check
    resp_live = await client.get("/health/live")
    resp_ready = await client.get("/health/ready")
    health_results = {
        "live": resp_live.json(),
        "ready": resp_ready.json(),
    }
    print(f"[+] Health Live: {resp_live.status_code} | Health Ready: {resp_ready.status_code}")

    concurrency_levels = [1, 10, 50, 100]
    total_reqs = 1000

    results: Dict[str, Any] = {
        "metadata": {
            "timestamp": time.time(),
            "git": get_git_metadata(),
            "hardware": get_hardware_environment(),
            "health_probes": health_results,
        },
        "exact_hit_benchmarks": [],
        "semantic_hit_benchmarks": [],
        "cache_miss_benchmarks": [],
        "mixed_workload_benchmarks": [],
        "customer_support_1000_benchmarks": [],
        "single_flight_coalescing": [],
    }

    # --- SCENARIO 1: EXACT CACHE HIT BENCHMARK ---
    print("\n" + "=" * 60)
    print(" [1/6] Running EXACT CACHE HIT Benchmarks (1000 requests each)")
    print("=" * 60)
    exact_payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "What is CacheMind distributed semantic caching architecture?"}], "temperature": 0.0}
    # Pre-populate exact cache
    await client.post("/v1/chat/completions", json=exact_payload, headers={"Authorization": f"Bearer {test_key}"})

    for c in concurrency_levels:
        summary, _ = await run_scenario(
            client=client,
            api_key=test_key,
            workload_items=[exact_payload],
            concurrency=c,
            total_requests=total_reqs,
            scenario_name=f"Exact Hit c={c}",
        )
        print(f"  Exact Hit (c={c:>3}): RPS={summary.throughput_rps:>8.1f} | p50={summary.client_latency_stats['p50']:>6.2f}ms | p95={summary.client_latency_stats['p95']:>6.2f}ms | p99={summary.client_latency_stats['p99']:>6.2f}ms | HitRate={summary.exact_hit_rate_pct:.1f}%")
        results["exact_hit_benchmarks"].append({"concurrency": c, "summary": asdict(summary)})

    # --- SCENARIO 2: SEMANTIC CACHE HIT BENCHMARK ---
    print("\n" + "=" * 60)
    print(" [2/6] Running SEMANTIC CACHE HIT Benchmarks (1000 requests each)")
    print("=" * 60)
    # Seed semantic cache with a canonical entry
    seed_payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Explain how to configure an asynchronous redis cache cluster in python"}], "temperature": 0.0}
    await client.post("/v1/chat/completions", json=seed_payload, headers={"Authorization": f"Bearer {test_key}"})

    # Paraphrased queries that trigger L2 semantic cache hits
    semantic_paraphrases = [
        {"model": "gpt-4o", "messages": [{"role": "user", "content": "How do I setup an async redis cluster in python?"}], "temperature": 0.0},
        {"model": "gpt-4o", "messages": [{"role": "user", "content": "Show me how to configure an asynchronous redis cache cluster with python."}], "temperature": 0.0},
        {"model": "gpt-4o", "messages": [{"role": "user", "content": "How can one configure async redis clustering in python?"}], "temperature": 0.0},
    ]

    for c in concurrency_levels:
        summary, _ = await run_scenario(
            client=client,
            api_key=test_key,
            workload_items=semantic_paraphrases,
            concurrency=c,
            total_requests=total_reqs,
            scenario_name=f"Semantic Hit c={c}",
        )
        print(f"  Semantic Hit (c={c:>3}): RPS={summary.throughput_rps:>8.1f} | p50={summary.client_latency_stats['p50']:>6.2f}ms | p95={summary.client_latency_stats['p95']:>6.2f}ms | p99={summary.client_latency_stats['p99']:>6.2f}ms | HitRate={summary.semantic_hit_rate_pct:.1f}%")
        results["semantic_hit_benchmarks"].append({"concurrency": c, "summary": asdict(summary)})

    # --- SCENARIO 3: CACHE MISS BENCHMARK ---
    print("\n" + "=" * 60)
    print(" [3/6] Running CACHE MISS Benchmarks (1000 unique requests each, simulated 35ms upstream LLM delay)")
    print("=" * 60)
    miss_queries = [
        {"model": "gpt-4o", "messages": [{"role": "user", "content": f"Unique prompt query token index {i} - {hashlib.sha256(str(i).encode()).hexdigest()[:12]}"}], "temperature": 0.0}
        for i in range(1000)
    ]

    for c in concurrency_levels:
        summary, _ = await run_scenario(
            client=client,
            api_key=test_key,
            workload_items=miss_queries,
            concurrency=c,
            total_requests=total_reqs,
            scenario_name=f"Cache Miss c={c}",
        )
        print(f"  Cache Miss (c={c:>3}): RPS={summary.throughput_rps:>8.1f} | p50={summary.client_latency_stats['p50']:>6.2f}ms | p95={summary.client_latency_stats['p95']:>6.2f}ms | p99={summary.client_latency_stats['p99']:>6.2f}ms | MissRate={summary.miss_count/summary.successful_requests*100:.1f}%")
        results["cache_miss_benchmarks"].append({"concurrency": c, "summary": asdict(summary)})

    # --- SCENARIO 4: MIXED WORKLOAD BENCHMARK (40% Exact, 35% Semantic, 25% Miss) ---
    print("\n" + "=" * 60)
    print(" [4/6] Running MIXED WORKLOAD Benchmarks (1000 requests each)")
    print("=" * 60)
    mixed_workload = []
    # 40% exact hits
    for _ in range(400):
        mixed_workload.append(exact_payload)
    # 35% semantic hits
    for i in range(350):
        mixed_workload.append(semantic_paraphrases[i % len(semantic_paraphrases)])
    # 25% unique misses
    for i in range(250):
        mixed_workload.append({"model": "gpt-4o", "messages": [{"role": "user", "content": f"Mixed unique prompt {i} {hashlib.md5(str(i).encode()).hexdigest()[:8]}"}], "temperature": 0.0})

    import random
    random.seed(42)
    random.shuffle(mixed_workload)

    for c in concurrency_levels:
        summary, _ = await run_scenario(
            client=client,
            api_key=test_key,
            workload_items=mixed_workload,
            concurrency=c,
            total_requests=total_reqs,
            scenario_name=f"Mixed c={c}",
        )
        print(f"  Mixed Workload (c={c:>3}): RPS={summary.throughput_rps:>8.1f} | p50={summary.client_latency_stats['p50']:>6.2f}ms | p95={summary.client_latency_stats['p95']:>6.2f}ms | ExactHit={summary.exact_hit_rate_pct:.1f}% | SemanticHit={summary.semantic_hit_rate_pct:.1f}% | OverallHit={summary.overall_hit_rate_pct:.1f}%")
        results["mixed_workload_benchmarks"].append({"concurrency": c, "summary": asdict(summary)})

    # --- SCENARIO 5: REALISTIC 1,000-QUERY CUSTOMER SUPPORT WORKLOAD ---
    print("\n" + "=" * 60)
    print(" [5/6] Running 1,000-QUERY CUSTOMER SUPPORT Workload @ c=10, 50, 100")
    print("=" * 60)
    cs_file = PROJECT_ROOT / "benchmarks" / "workloads" / "customer_support_1000.jsonl"
    cs_queries = [json.loads(line) for line in cs_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    for c in [10, 50, 100]:
        summary, _ = await run_scenario(
            client=client,
            api_key=test_key,
            workload_items=cs_queries,
            concurrency=c,
            total_requests=len(cs_queries),
            scenario_name=f"Customer Support c={c}",
        )
        print(f"  Customer Support 1k (c={c:>3}): RPS={summary.throughput_rps:>8.1f} | p50={summary.client_latency_stats['p50']:>6.2f}ms | p95={summary.client_latency_stats['p95']:>6.2f}ms | ExactHit={summary.exact_hit_rate_pct:.1f}% | SemanticHit={summary.semantic_hit_rate_pct:.1f}% | TotalHit={summary.overall_hit_rate_pct:.1f}%")
        results["customer_support_1000_benchmarks"].append({"concurrency": c, "summary": asdict(summary)})

    # --- SCENARIO 6: SINGLE-FLIGHT COALESCING PROOF ---
    print("\n" + "=" * 60)
    print(" [6/6] Running SINGLE-FLIGHT REQUEST COALESCING Concurrency Proof @ c=10, 50, 100")
    print("=" * 60)
    for c in [10, 50, 100]:
        coalesce_res = await run_coalescing_proof(
            base_url="http://benchmark",
            api_key=test_key,
            concurrency=c,
            prompt=f"Explain zero-copy socket buffers in Linux kernel under high throughput network traffic (concurrency run {c}).",
            client=client,
        )
        results["single_flight_coalescing"].append(coalesce_res)

    await client.aclose()

    # Save results to benchmarks/results/
    out_dir = PROJECT_ROOT / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "gateway_benchmark_suite.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\n" + "=" * 80)
    print(f" [+] Full Benchmark Suite JSON Artifact successfully saved to: {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main_benchmark())
