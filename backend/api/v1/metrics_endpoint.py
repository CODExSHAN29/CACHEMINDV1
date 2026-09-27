from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST

from backend.metrics.collector import get_metrics_collector

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def get_metrics() -> Response:
    """
    Exposes Prometheus metrics for Prometheus scraping / OpenMetrics monitoring.
    """
    collector = get_metrics_collector()
    metrics_data = collector.export()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
