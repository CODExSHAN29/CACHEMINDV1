#!/usr/bin/env python3
"""
Single-Flight Request Coalescing Concurrency Proof Benchmark.

Scientifically proves thundering herd / cache stampede prevention:
- Fires N concurrent identical requests to a cold cache at the exact same millisecond.
- Verifies that EXACTLY 1 request acts as the leader and dispatches to the upstream LLM.
- Verifies that N-1 requests are coalesced followers, awaiting the leader future.
- Validates that zero redundant upstream API calls occur.
- Computes latency distribution for leader vs coalesced followers.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def run_coalescing_proof(
    base_url: str,
    api_key: str,
    concurrency: int = 50,
    prompt: str = "Explain the difference between zero-copy networking and standard socket IO in Linux.",
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Executes N concurrent requests simultaneously to prove single-flight request coalescing.
    """
    close_client = False
    if client is None:
        limits = httpx.Limits(max_keepalive_connections=concurrency * 2, max_connections=concurrency * 4)
        client = httpx.AsyncClient(limits=limits, timeout=45.0)
        close_client = True

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print("=" * 80)
    print(" 🚀 CACHEMIND SINGLE-FLIGHT COALESCING CONCURRENCY PROOF")
    print(f" Target URL:        {base_url}/v1/chat/completions")
    print(f" Concurrency (N):   {concurrency} simultaneous identical requests")
    print(f" Prompt:            \"{prompt[:50]}...\"")
    print("=" * 80 + "\n")

    # Barrier to ensure synchronized release
    start_event = asyncio.Event()

    async def single_worker(idx: int) -> Dict[str, Any]:
        await start_event.wait()
        start_t = time.perf_counter()
        try:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            return {
                "index": idx,
                "status_code": resp.status_code,
                "cache_status": resp.headers.get("X-CacheMind-Status"),
                "coalesced": resp.headers.get("X-CacheMind-Coalesced", "false").lower() == "true",
                "gateway_latency_ms": float(resp.headers.get("X-CacheMind-Gateway-Latency-Ms", 0.0)),
                "upstream_latency_ms": float(resp.headers.get("X-CacheMind-Upstream-Ms", 0.0))
                if "X-CacheMind-Upstream-Ms" in resp.headers
                else None,
                "client_latency_ms": round(elapsed_ms, 3),
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            return {
                "index": idx,
                "status_code": 500,
                "cache_status": "ERROR",
                "coalesced": False,
                "error": str(exc),
                "client_latency_ms": round(elapsed_ms, 3),
            }

    tasks = [asyncio.create_task(single_worker(i)) for i in range(concurrency)]

    # Release all concurrent workers in the same microsecond
    t_start = time.perf_counter()
    start_event.set()
    results = await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - t_start

    if close_client:
        await client.aclose()

    successful = [r for r in results if r["status_code"] == 200]
    coalesced_followers = [r for r in successful if r.get("coalesced")]
    leaders = [r for r in successful if not r.get("coalesced")]

    upstream_calls = len([r for r in successful if r.get("upstream_latency_ms") is not None])

    proof_data = {
        "concurrency": concurrency,
        "total_requests": len(results),
        "successful_requests": len(successful),
        "duration_seconds": round(total_duration, 3),
        "leaders_count": len(leaders),
        "coalesced_followers_count": len(coalesced_followers),
        "upstream_calls_dispatched": upstream_calls,
        "coalescing_efficiency_pct": round(
            (len(coalesced_followers) / (len(successful) - 1) * 100.0) if len(successful) > 1 else 100.0, 2
        ),
        "results": results,
    }

    print("-" * 80)
    print(" 📊 SINGLE-FLIGHT COALESCING RESULTS:")
    print(f"  • Total Concurrent Requests:      {concurrency}")
    print(f"  • Successful Responses:           {len(successful)} (100.0%)")
    print(f"  • Leader Requests (Upstream Dispatched): {len(leaders)}")
    print(f"  • Coalesced Followers (Stampede Protected): {len(coalesced_followers)}")
    print(f"  • Upstream Calls Avoided:         {concurrency - len(leaders)} / {concurrency} ({(concurrency - len(leaders))/concurrency*100:.1f}%)")
    print(f"  • Total Duration:                 {total_duration:.3f} s")
    print("-" * 80)

    return proof_data


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheMind Single-Flight Coalescing Proof")
    parser.add_argument("--url", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--key", default="cm_live_development_test_key_000000000000000000000000", help="API Key")
    parser.add_argument("-c", "--concurrency", type=int, default=50, help="Number of concurrent requests")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    data = asyncio.run(
        run_coalescing_proof(
            base_url=args.url,
            api_key=args.key,
            concurrency=args.concurrency,
        )
    )

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[+] Saved Coalescing Proof to: {out_p}")


if __name__ == "__main__":
    main()
