#!/usr/bin/env python3
"""
CacheMind Gateway — Reproducible Latency & Throughput Benchmark Harness.

Measures:
- Cold-start latency vs Warm steady-state latency
- Exact L1 cache hit latency (< 2.0ms target)
- Semantic L2 vector cache hit latency (< 8.0ms target)
- Upstream LLM dispatch latency on cache misses
- Single-flight coalescing under concurrency
- Hardware and Git environment capture for scientific reproducibility
"""

import argparse
import asyncio
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Ensure backend root is in sys.path for direct imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class RequestRecord:
    timestamp: float
    request_index: int
    prompt_preview: str
    status_code: int
    cache_status: str
    client_latency_ms: float
    gateway_latency_ms: Optional[float]
    lookup_latency_ms: Optional[float]
    upstream_latency_ms: Optional[float]
    similarity: Optional[float]
    coalesced: bool
    is_cold_start: bool
    error: Optional[str] = None


@dataclass
class BenchmarkSummary:
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_seconds: float
    throughput_rps: float
    exact_hit_count: int
    semantic_hit_count: int
    miss_count: int
    exact_hit_rate_pct: float
    semantic_hit_rate_pct: float
    overall_hit_rate_pct: float
    cold_start_latency_ms: Optional[float]
    client_latency_stats: Dict[str, float]
    exact_hit_latency_stats: Dict[str, float]
    semantic_hit_latency_stats: Dict[str, float]
    miss_latency_stats: Dict[str, float]
    lookup_latency_stats: Dict[str, float]


def get_git_metadata() -> Dict[str, Any]:
    """Extracts git commit hash, branch, and status."""
    meta: Dict[str, Any] = {"commit": "unknown", "branch": "unknown", "dirty": False}
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL
        ).decode().strip()
        meta["commit"] = commit
    except Exception:
        pass

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL
        ).decode().strip()
        meta["branch"] = branch
    except Exception:
        pass

    try:
        status_out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL
        ).decode().strip()
        meta["dirty"] = len(status_out) > 0
    except Exception:
        pass

    return meta


def get_hardware_environment() -> Dict[str, Any]:
    """Captures CPU, RAM, OS, and Python environment metadata."""
    env = {
        "os": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "architecture": platform.architecture()[0],
        "processor": platform.processor() or platform.machine(),
        "python_version": platform.python_version(),
        "python_compiler": platform.python_compiler(),
        "cpu_count": os.cpu_count(),
    }
    try:
        import psutil
        mem = psutil.virtual_memory()
        env["total_ram_gb"] = round(mem.total / (1024 ** 3), 2)
        env["available_ram_gb"] = round(mem.available / (1024 ** 3), 2)
    except ImportError:
        env["total_ram_gb"] = "psutil_not_installed"

    try:
        import onnxruntime
        env["onnxruntime_version"] = onnxruntime.__version__
    except ImportError:
        env["onnxruntime_version"] = "not_installed"

    return env


def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculates min, max, mean, stddev, p50, p90, p95, p99 percentiles."""
    if not values:
        return {"min": 0.0, "mean": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "stddev": 0.0}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def p(pct: float) -> float:
        idx = min(int(n * pct / 100.0), n - 1)
        return sorted_vals[idx]

    stddev = statistics.stdev(values) if len(values) > 1 else 0.0

    return {
        "min": round(min(sorted_vals), 3),
        "mean": round(statistics.mean(sorted_vals), 3),
        "stddev": round(stddev, 3),
        "p50": round(statistics.median(sorted_vals), 3),
        "p90": round(p(90), 3),
        "p95": round(p(95), 3),
        "p99": round(p(99), 3),
        "max": round(max(sorted_vals), 3),
    }


async def send_benchmark_request(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    payload: Dict[str, Any],
    req_index: int,
    is_cold_start: bool = False,
) -> RequestRecord:
    """Executes a single chat completion request and records telemetry headers."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    user_msg = ""
    for msg in payload.get("messages", []):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    preview = user_msg[:40].replace("\n", " ")

    start_ns = time.perf_counter_ns()
    try:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

        cache_status = response.headers.get("X-CacheMind-Status", "UNKNOWN")
        gw_lat = response.headers.get("X-CacheMind-Gateway-Latency-Ms")
        lookup_lat = response.headers.get("X-CacheMind-Lookup-Ms")
        upstream_lat = response.headers.get("X-CacheMind-Upstream-Ms")
        similarity = response.headers.get("X-CacheMind-Similarity")
        coalesced = response.headers.get("X-CacheMind-Coalesced", "false").lower() == "true"

        return RequestRecord(
            timestamp=time.time(),
            request_index=req_index,
            prompt_preview=preview,
            status_code=response.status_code,
            cache_status=cache_status,
            client_latency_ms=round(elapsed_ms, 3),
            gateway_latency_ms=float(gw_lat) if gw_lat is not None else None,
            lookup_latency_ms=float(lookup_lat) if lookup_lat is not None else None,
            upstream_latency_ms=float(upstream_lat) if upstream_lat is not None else None,
            similarity=float(similarity) if similarity is not None else None,
            coalesced=coalesced,
            is_cold_start=is_cold_start,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        return RequestRecord(
            timestamp=time.time(),
            request_index=req_index,
            prompt_preview=preview,
            status_code=500,
            cache_status="ERROR",
            client_latency_ms=round(elapsed_ms, 3),
            gateway_latency_ms=None,
            lookup_latency_ms=None,
            upstream_latency_ms=None,
            similarity=None,
            coalesced=False,
            is_cold_start=is_cold_start,
            error=str(exc),
        )


def load_workload(workload_path: Path) -> List[Dict[str, Any]]:
    """Loads JSONL requests from a file."""
    requests: List[Dict[str, Any]] = []
    with open(workload_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                requests.append(json.loads(line))
    return requests


async def run_benchmark(
    base_url: str,
    api_key: str,
    workload_path: Path,
    concurrency: int = 20,
    iterations: int = 100,
    warmup_count: int = 5,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[BenchmarkSummary, List[RequestRecord]]:
    """Runs a full benchmark suite over the specified workload."""
    workload_items = load_workload(workload_path)
    if not workload_items:
        raise ValueError(f"No items found in workload {workload_path}")

    close_client = False
    if client is None:
        limits = httpx.Limits(max_keepalive_connections=concurrency * 2, max_connections=concurrency * 4)
        client = httpx.AsyncClient(limits=limits, timeout=45.0)
        close_client = True

    records: List[RequestRecord] = []

    try:
        # Step 1: Measure Cold Start (Request #0)
        print(f"[*] Measuring Cold-Start Request on {workload_items[0]['messages'][0]['content'][:30]}...")
        cold_record = await send_benchmark_request(
            client=client,
            base_url=base_url,
            api_key=api_key,
            payload=workload_items[0],
            req_index=0,
            is_cold_start=True,
        )
        records.append(cold_record)
        print(f"    -> Cold-Start Status: {cold_record.cache_status} in {cold_record.client_latency_ms:.2f}ms")

        # Step 2: Warm-up Phase
        if warmup_count > 0:
            print(f"[*] Running Warm-up Phase ({warmup_count} requests)...")
            for i in range(warmup_count):
                payload = workload_items[i % len(workload_items)]
                await send_benchmark_request(
                    client=client,
                    base_url=base_url,
                    api_key=api_key,
                    payload=payload,
                    req_index=-(i + 1),
                    is_cold_start=False,
                )

        # Step 3: Steady-State Concurrent Benchmark
        print(f"[*] Running Steady-State Benchmark ({iterations} requests @ concurrency={concurrency})...")
        sem = asyncio.Semaphore(concurrency)

        async def worker(idx: int) -> RequestRecord:
            async with sem:
                payload = workload_items[idx % len(workload_items)]
                rec = await send_benchmark_request(
                    client=client,
                    base_url=base_url,
                    api_key=api_key,
                    payload=payload,
                    req_index=idx + 1,
                    is_cold_start=False,
                )
                return rec

        benchmark_start = time.perf_counter()
        tasks = [worker(i) for i in range(iterations)]
        bench_records = await asyncio.gather(*tasks)
        benchmark_duration = time.perf_counter() - benchmark_start

        records.extend(bench_records)

        # Compute Summary Statistics (excluding warmup)
        eval_records = [r for r in records if r.request_index > 0]
        successful = [r for r in eval_records if r.status_code == 200]
        failed = [r for r in eval_records if r.status_code != 200]

        exact_records = [r for r in successful if r.cache_status == "EXACT_HIT"]
        semantic_records = [r for r in successful if r.cache_status == "L2_HIT"]
        miss_records = [r for r in successful if r.cache_status == "MISS"]

        exact_count = len(exact_records)
        semantic_count = len(semantic_records)
        miss_count = len(miss_records)
        total_eval = len(eval_records)

        exact_hit_rate = (exact_count / total_eval * 100.0) if total_eval > 0 else 0.0
        semantic_hit_rate = (semantic_count / total_eval * 100.0) if total_eval > 0 else 0.0
        overall_hit_rate = ((exact_count + semantic_count) / total_eval * 100.0) if total_eval > 0 else 0.0
        throughput = total_eval / benchmark_duration if benchmark_duration > 0 else 0.0

        all_latencies = [r.client_latency_ms for r in successful]
        exact_latencies = [r.client_latency_ms for r in exact_records]
        semantic_latencies = [r.client_latency_ms for r in semantic_records]
        miss_latencies = [r.client_latency_ms for r in miss_records]
        lookup_latencies = [r.lookup_latency_ms for r in successful if r.lookup_latency_ms is not None]

        summary = BenchmarkSummary(
            total_requests=total_eval,
            successful_requests=len(successful),
            failed_requests=len(failed),
            duration_seconds=round(benchmark_duration, 3),
            throughput_rps=round(throughput, 1),
            exact_hit_count=exact_count,
            semantic_hit_count=semantic_count,
            miss_count=miss_count,
            exact_hit_rate_pct=round(exact_hit_rate, 2),
            semantic_hit_rate_pct=round(semantic_hit_rate, 2),
            overall_hit_rate_pct=round(overall_hit_rate, 2),
            cold_start_latency_ms=cold_record.client_latency_ms,
            client_latency_stats=calculate_stats(all_latencies),
            exact_hit_latency_stats=calculate_stats(exact_latencies),
            semantic_hit_latency_stats=calculate_stats(semantic_latencies),
            miss_latency_stats=calculate_stats(miss_latencies),
            lookup_latency_stats=calculate_stats(lookup_latencies),
        )

        return summary, records
    finally:
        if close_client:
            await client.aclose()


def print_summary_report(summary: BenchmarkSummary, workload_name: str, concurrency: int) -> None:
    """Prints a professional, structured benchmark report to stdout."""
    print("\n" + "=" * 80)
    print(f" 🚀 CACHEMIND BENCHMARK REPORT — Workload: {workload_name} (Concurrency: {concurrency})")
    print("=" * 80)
    print(f" Total Requests:    {summary.total_requests}")
    print(f" Successful:        {summary.successful_requests} ({summary.successful_requests/summary.total_requests*100:.1f}%)")
    print(f" Duration:          {summary.duration_seconds:.3f} s")
    print(f" Throughput:        {summary.throughput_rps:.1f} req/sec")
    print(f" Cold-Start Time:   {summary.cold_start_latency_ms:.2f} ms")
    print("-" * 80)
    print(" 🎯 CACHE HIT METRICS:")
    print(f"  • L1 Exact Hits:       {summary.exact_hit_count:5d} ({summary.exact_hit_rate_pct:5.1f}%)")
    print(f"  • L2 Semantic Hits:    {summary.semantic_hit_count:5d} ({summary.semantic_hit_rate_pct:5.1f}%)")
    print(f"  • Cache Misses:        {summary.miss_count:5d} ({(summary.miss_count/summary.total_requests*100 if summary.total_requests else 0):5.1f}%)")
    print(f"  • Overall Hit Rate:    {summary.overall_hit_rate_pct:5.1f}%")
    print("-" * 80)
    print(" ⏱️ LATENCY PERCENTILES (Client-Observed Milliseconds):")
    headers = f"{'Category':<18} | {'p50':>7} | {'p90':>7} | {'p95':>7} | {'p99':>7} | {'Mean':>7} | {'Min':>7} | {'Max':>7}"
    print(headers)
    print("-" * len(headers))

    for label, stats in [
        ("All Requests", summary.client_latency_stats),
        ("L1 Exact Hits", summary.exact_hit_latency_stats),
        ("L2 Semantic Hits", summary.semantic_hit_latency_stats),
        ("Cache Misses", summary.miss_latency_stats),
        ("Internal Lookup", summary.lookup_latency_stats),
    ]:
        if stats["mean"] > 0 or stats["max"] > 0:
            row = (
                f"{label:<18} | "
                f"{stats['p50']:7.2f} | "
                f"{stats['p90']:7.2f} | "
                f"{stats['p95']:7.2f} | "
                f"{stats['p99']:7.2f} | "
                f"{stats['mean']:7.2f} | "
                f"{stats['min']:7.2f} | "
                f"{stats['max']:7.2f}"
            )
            print(row)

    print("=" * 80 + "\n")


def generate_json_output(
    summary: BenchmarkSummary,
    records: List[RequestRecord],
    workload_name: str,
    concurrency: int,
    output_path: Path,
) -> None:
    """Saves benchmark results, hardware env, and raw records to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "benchmark_metadata": {
            "workload": workload_name,
            "concurrency": concurrency,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git": get_git_metadata(),
            "hardware": get_hardware_environment(),
        },
        "summary": asdict(summary),
        "raw_records": [asdict(r) for r in records],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[+] Saved structured benchmark JSON to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheMind Gateway Benchmark Harness")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of CacheMind Gateway")
    parser.add_argument("--key", default="cm_live_development_test_key_000000000000000000000000", help="API Key")
    parser.add_argument("--workload", default="exact", help="Workload profile name or file (e.g. exact, semantic, mixed, customer_support_1000)")
    parser.add_argument("-c", "--concurrency", type=int, default=20, help="Concurrency level")
    parser.add_argument("-n", "--iterations", type=int, default=100, help="Number of benchmark iterations")
    parser.add_argument("--warmup", type=int, default=5, help="Number of warmup iterations")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    workload_file = PROJECT_ROOT / "benchmarks" / "workloads" / f"{args.workload}.jsonl"
    if not workload_file.exists():
        print(f"[-] Workload file not found: {workload_file}", file=sys.stderr)
        sys.exit(1)

    summary, records = asyncio.run(
        run_benchmark(
            base_url=args.url,
            api_key=args.key,
            workload_path=workload_file,
            concurrency=args.concurrency,
            iterations=args.iterations,
            warmup_count=args.warmup,
        )
    )

    print_summary_report(summary, args.workload, args.concurrency)

    out_path = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT / "benchmarks" / "results" / f"{args.workload}_c{args.concurrency}_{int(time.time())}.json"
    )
    generate_json_output(summary, records, args.workload, args.concurrency, out_path)


if __name__ == "__main__":
    main()
