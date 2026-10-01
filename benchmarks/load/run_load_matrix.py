#!/usr/bin/env python3
"""
CacheMind Load Testing Matrix Runner.

Executes concurrent load testing sweeps across 10, 50, and 100 concurrent clients
over standard CacheMind workloads (exact, semantic, mixed).
Captures throughput, latency percentiles (p50, p90, p95, p99), error rates,
and outputs structured results to JSON for reporting.
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.benchmark_gateway import (
    BenchmarkSummary,
    get_git_metadata,
    get_hardware_environment,
    print_summary_report,
    run_benchmark,
)


async def run_load_matrix(
    base_url: str,
    api_key: str,
    concurrency_levels: List[int] = [10, 50, 100],
    workloads: List[str] = ["exact", "semantic", "mixed"],
    iterations_per_run: int = 100,
    warmup_count: int = 5,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Executes a full matrix sweep across specified concurrency levels and workloads."""
    results_matrix: List[Dict[str, Any]] = []

    print("=" * 80)
    print(" 🚀 CACHEMIND CONCURRENT LOAD MATRIX SUITE")
    print(f" Concurrency Levels: {concurrency_levels}")
    print(f" Workloads:          {workloads}")
    print(f" Requests / Run:     {iterations_per_run}")
    print("=" * 80 + "\n")

    for workload in workloads:
        workload_file = PROJECT_ROOT / "benchmarks" / "workloads" / f"{workload}.jsonl"
        if not workload_file.exists():
            print(f"[-] Skipping missing workload: {workload_file}")
            continue

        for c in concurrency_levels:
            print(f"\n[▶] Starting Run: Workload='{workload}' | Concurrency={c} | Requests={iterations_per_run}")
            summary, records = await run_benchmark(
                base_url=base_url,
                api_key=api_key,
                workload_path=workload_file,
                concurrency=c,
                iterations=iterations_per_run,
                warmup_count=warmup_count,
                client=client,
            )

            print_summary_report(summary, workload_name=workload, concurrency=c)

            run_entry = {
                "workload": workload,
                "concurrency": c,
                "summary": asdict(summary),
            }
            results_matrix.append(run_entry)

    matrix_output = {
        "metadata": {
            "timestamp": time.time(),
            "git": get_git_metadata(),
            "hardware": get_hardware_environment(),
            "concurrency_levels": concurrency_levels,
            "workloads": workloads,
            "iterations_per_run": iterations_per_run,
        },
        "runs": results_matrix,
    }

    return matrix_output


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheMind Concurrent Load Matrix Benchmark")
    parser.add_argument("--url", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--key", default="cm_live_development_test_key_000000000000000000000000", help="API Key")
    parser.add_argument("-c", "--concurrency", nargs="+", type=int, default=[10, 50, 100], help="Concurrency list")
    parser.add_argument("-w", "--workloads", nargs="+", default=["exact", "semantic", "mixed"], help="Workload list")
    parser.add_argument("-n", "--iterations", type=int, default=100, help="Requests per benchmark run")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup requests per run")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    results = asyncio.run(
        run_load_matrix(
            base_url=args.url,
            api_key=args.key,
            concurrency_levels=args.concurrency,
            workloads=args.workloads,
            iterations_per_run=args.iterations,
            warmup_count=args.warmup,
        )
    )

    out_file = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT / "benchmarks" / "results" / f"load_matrix_{int(time.time())}.json"
    )
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Full Load Matrix Benchmark saved to: {out_file}")


if __name__ == "__main__":
    main()
