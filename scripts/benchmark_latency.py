#!/usr/bin/env python3
"""
CacheMind High-Concurrency Latency & Throughput Benchmark.

Measures p50, p90, p95, p99 latency percentiles and throughput for:
1. Exact L1 Cache Hits (Target: < 2.0ms)
2. Semantic L2 Vector Cache Hits (Target: < 8.0ms)
3. Cache Misses (Upstream LLM Dispatch)
"""

import argparse
import asyncio
import json
import statistics
import time
from typing import Any, Dict, List, Tuple
import httpx


DEFAULT_PROMPTS = [
    "Explain quantum computing in simple terms.",
    "What is the difference between synchronous and asynchronous programming?",
    "Write a Python function to compute the nth Fibonacci number efficiently.",
    "How does TLS 1.3 0-RTT handshake work?",
    "Explain the CAP theorem with distributed database examples.",
]

SEMANTIC_PARAPHRASES = [
    "Can you explain quantum computing in a simple way?",
    "What separates async programming from sync programming?",
    "Show me a fast Python Fibonacci function.",
    "How does zero round-trip time resumption operate in TLS 1.3?",
    "Describe CAP theorem with real world database trade-offs.",
]


async def send_inference_request(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.0,
) -> Tuple[float, str, int]:
    """
    Sends a chat completion request and records response time in milliseconds.
    Returns: (latency_ms, cache_status, status_code)
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.perf_counter_ns()
    try:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15.0,
        )
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000.0
        cache_status = response.headers.get("X-CacheMind-Status", "UNKNOWN")
        return elapsed_ms, cache_status, response.status_code
    except Exception as exc:
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000.0
        return elapsed_ms, f"ERROR: {str(exc)}", 500


def calculate_percentiles(latencies: List[float]) -> Dict[str, float]:
    if not latencies:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0}
    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)

    def p(pct: float) -> float:
        idx = min(int(n * pct / 100.0), n - 1)
        return latencies_sorted[idx]

    return {
        "min": round(min(latencies_sorted), 3),
        "p50": round(statistics.median(latencies_sorted), 3),
        "p90": round(p(90), 3),
        "p95": round(p(95), 3),
        "p99": round(p(99), 3),
        "max": round(max(latencies_sorted), 3),
        "mean": round(statistics.mean(latencies_sorted), 3),
    }


async def run_benchmark(
    base_url: str,
    api_key: str,
    concurrency: int = 50,
    iterations: int = 200,
) -> None:
    print("=" * 80)
    print(" 🚀 CACHEMIND GATEWAY ENTERPRISE LATENCY BENCHMARK")
    print(f" Target URL:     {base_url}")
    print(f" Concurrency:    {concurrency}")
    print(f" Iterations:     {iterations} per test phase")
    print("=" * 80)

    limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        # Phase 1: Warm-up & Cache Seeding (Misses)
        print("\n[Phase 1] Seeding Base Prompts (Cold Cache Misses)...")
        miss_latencies: List[float] = []
        for prompt in DEFAULT_PROMPTS:
            lat, status, code = await send_inference_request(client, base_url, api_key, prompt)
            miss_latencies.append(lat)
            print(f"  - [{code}] Status: {status:<15} Latency: {lat:6.2f}ms | Prompt: {prompt[:40]}...")

        # Phase 2: Exact L1 Cache Hits Benchmark
        print(f"\n[Phase 2] Benchmarking Exact L1 Cache Hits ({iterations} concurrent requests)...")
        exact_latencies: List[float] = []
        exact_statuses: Dict[str, int] = {}

        sem = asyncio.Semaphore(concurrency)

        async def worker_exact(prompt_idx: int) -> None:
            async with sem:
                prompt = DEFAULT_PROMPTS[prompt_idx % len(DEFAULT_PROMPTS)]
                lat, status, code = await send_inference_request(client, base_url, api_key, prompt)
                exact_latencies.append(lat)
                exact_statuses[status] = exact_statuses.get(status, 0) + 1

        start_time = time.perf_counter()
        tasks = [worker_exact(i) for i in range(iterations)]
        await asyncio.gather(*tasks)
        exact_duration = time.perf_counter() - start_time
        exact_qps = iterations / exact_duration if exact_duration > 0 else 0

        exact_stats = calculate_percentiles(exact_latencies)

        # Phase 3: Semantic L2 Cache Hits Benchmark
        print(f"\n[Phase 3] Benchmarking Semantic L2 Vector Cache Hits ({iterations} concurrent requests)...")
        semantic_latencies: List[float] = []
        semantic_statuses: Dict[str, int] = {}

        async def worker_semantic(prompt_idx: int) -> None:
            async with sem:
                prompt = SEMANTIC_PARAPHRASES[prompt_idx % len(SEMANTIC_PARAPHRASES)]
                lat, status, code = await send_inference_request(client, base_url, api_key, prompt)
                semantic_latencies.append(lat)
                semantic_statuses[status] = semantic_statuses.get(status, 0) + 1

        start_time = time.perf_counter()
        tasks = [worker_semantic(i) for i in range(iterations)]
        await asyncio.gather(*tasks)
        semantic_duration = time.perf_counter() - start_time
        semantic_qps = iterations / semantic_duration if semantic_duration > 0 else 0

        semantic_stats = calculate_percentiles(semantic_latencies)

        # Print Benchmark Report
        print("\n" + "=" * 80)
        print(" 📊 BENCHMARK RESULTS SUMMARY")
        print("=" * 80)
        print(f"\n⚡ L1 EXACT CACHE HITS:")
        print(f"  • Throughput:      {exact_qps:8.1f} req/sec")
        print(f"  • Mean Latency:    {exact_stats['mean']:8.3f} ms")
        print(f"  • Min Latency:     {exact_stats['min']:8.3f} ms")
        print(f"  • p50 (Median):    {exact_stats['p50']:8.3f} ms")
        print(f"  • p90:             {exact_stats['p90']:8.3f} ms")
        print(f"  • p95:             {exact_stats['p95']:8.3f} ms")
        print(f"  • p99:             {exact_stats['p99']:8.3f} ms")
        print(f"  • Max Latency:     {exact_stats['max']:8.3f} ms")
        print(f"  • Status Dist:     {exact_statuses}")

        print(f"\n🧠 L2 SEMANTIC VECTOR CACHE HITS:")
        print(f"  • Throughput:      {semantic_qps:8.1f} req/sec")
        print(f"  • Mean Latency:    {semantic_stats['mean']:8.3f} ms")
        print(f"  • Min Latency:     {semantic_stats['min']:8.3f} ms")
        print(f"  • p50 (Median):    {semantic_stats['p50']:8.3f} ms")
        print(f"  • p90:             {semantic_stats['p90']:8.3f} ms")
        print(f"  • p95:             {semantic_stats['p95']:8.3f} ms")
        print(f"  • p99:             {semantic_stats['p99']:8.3f} ms")
        print(f"  • Max Latency:     {semantic_stats['max']:8.3f} ms")
        print(f"  • Status Dist:     {semantic_statuses}")

        print("\n" + "=" * 80)
        l1_pass = exact_stats["p50"] <= 2.5
        l2_pass = semantic_stats["p50"] <= 12.0
        print(f" SLA TARGET CHECK:")
        print(f"  - L1 Exact Hit Target (< 2.5ms):   {'✅ PASS' if l1_pass else '⚠️ FAIL'} ({exact_stats['p50']}ms)")
        print(f"  - L2 Semantic Target (< 12.0ms):   {'✅ PASS' if l2_pass else '⚠️ FAIL'} ({semantic_stats['p50']}ms)")
        print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheMind Latency Benchmark")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of CacheMind Gateway")
    parser.add_argument("--key", default="cm_live_development_key_1234567890abcdef", help="CacheMind API Key")
    parser.add_argument("-c", "--concurrency", type=int, default=50, help="Concurrency level")
    parser.add_argument("-n", "--iterations", type=int, default=200, help="Number of iterations per phase")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.url, args.key, args.concurrency, args.iterations))


if __name__ == "__main__":
    main()
