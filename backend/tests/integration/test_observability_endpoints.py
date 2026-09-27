import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_endpoint_scraping(async_client: AsyncClient, tenant_a_fixtures: dict):
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    # Send a request to trigger metrics recording
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Ping test metrics"}],
        "temperature": 0.0,
    }
    chat_res = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert chat_res.status_code == 200

    # Scrape /metrics endpoint
    metrics_res = await async_client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "text/plain" in metrics_res.headers.get("content-type", "")

    metrics_text = metrics_res.text
    assert "cachemind_requests_total" in metrics_text
    assert "cachemind_gateway_latency_seconds" in metrics_text
    assert "cachemind_tokens_processed_total" in metrics_text


@pytest.mark.asyncio
async def test_dashboard_endpoint_rendering(async_client: AsyncClient):
    # Fetch /dashboard HTML UI
    dashboard_res = await async_client.get("/dashboard")
    assert dashboard_res.status_code == 200
    assert "text/html" in dashboard_res.headers.get("content-type", "")

    html_content = dashboard_res.text
    assert "CacheMind" in html_content
    assert "Observability Dashboard" in html_content
    assert "timeseriesChart" in html_content
    assert "modelsChart" in html_content
    assert "logsTableBody" in html_content
