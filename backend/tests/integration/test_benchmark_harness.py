import pytest
from pathlib import Path
from httpx import AsyncClient

from benchmarks.benchmark_gateway import run_benchmark, PROJECT_ROOT


@pytest.mark.asyncio
async def test_benchmark_exact_workload_in_process(async_client: AsyncClient, tenant_a_fixtures: dict):
    workload_file = PROJECT_ROOT / "benchmarks" / "workloads" / "exact.jsonl"
    assert workload_file.exists()

    summary, records = await run_benchmark(
        base_url="http://test",
        api_key=tenant_a_fixtures["raw_key"],
        workload_path=workload_file,
        concurrency=5,
        iterations=20,
        warmup_count=2,
        client=async_client,
    )

    assert summary.total_requests == 20
    assert summary.successful_requests == 20
    assert summary.failed_requests == 0
    assert summary.overall_hit_rate_pct > 0.0
    assert summary.client_latency_stats["p50"] > 0.0
    assert len(records) > 0


@pytest.mark.asyncio
async def test_benchmark_mixed_workload_in_process(async_client: AsyncClient, tenant_a_fixtures: dict):
    workload_file = PROJECT_ROOT / "benchmarks" / "workloads" / "mixed.jsonl"
    assert workload_file.exists()

    summary, records = await run_benchmark(
        base_url="http://test",
        api_key=tenant_a_fixtures["raw_key"],
        workload_path=workload_file,
        concurrency=5,
        iterations=20,
        warmup_count=2,
        client=async_client,
    )

    assert summary.total_requests == 20
    assert summary.successful_requests == 20
    assert summary.failed_requests == 0


@pytest.mark.asyncio
async def test_load_matrix_runner_in_process(async_client: AsyncClient, tenant_a_fixtures: dict):
    from benchmarks.load.run_load_matrix import run_load_matrix

    matrix_res = await run_load_matrix(
        base_url="http://test",
        api_key=tenant_a_fixtures["raw_key"],
        concurrency_levels=[2, 4],
        workloads=["exact"],
        iterations_per_run=10,
        warmup_count=1,
        client=async_client,
    )

    assert "metadata" in matrix_res
    assert len(matrix_res["runs"]) == 2
    for run in matrix_res["runs"]:
        assert run["summary"]["successful_requests"] == 10
        assert run["summary"]["failed_requests"] == 0

