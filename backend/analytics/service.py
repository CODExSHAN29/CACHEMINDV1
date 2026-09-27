from datetime import datetime, timezone, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analytics.models import (
    AnalyticsOverview,
    ModelUsageMetrics,
    PaginatedLogsResponse,
    RequestLogItem,
    TimeseriesPoint,
)
from backend.analytics.pricing import PricingEngine
from backend.db.models import RequestLog


class AnalyticsService:
    """
    Analytics and Cost Accounting Service.
    Aggregates request telemetry, computes token and dollar savings,
    calculates latency percentiles, and generates timeseries metrics.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_overview(
        self,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> AnalyticsOverview:
        """
        Computes high-level KPI overview across filtered criteria.
        """
        stmt = select(RequestLog)

        if tenant_id:
            stmt = stmt.where(RequestLog.tenant_id == tenant_id)
        if project_id:
            stmt = stmt.where(RequestLog.project_id == project_id)
        if start_time:
            stmt = stmt.where(RequestLog.created_at >= start_time)
        if end_time:
            stmt = stmt.where(RequestLog.created_at <= end_time)

        result = await self.session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return AnalyticsOverview()

        total_requests = len(logs)
        exact_hits = sum(1 for log in logs if log.cache_status == "EXACT_HIT")
        semantic_hits = sum(1 for log in logs if log.cache_status == "L2_HIT")
        total_hits = exact_hits + semantic_hits
        misses = sum(1 for log in logs if log.cache_status == "MISS")
        errors = sum(1 for log in logs if log.cache_status in ("ERROR", "BYPASS"))

        hit_rate_pct = round((total_hits / total_requests) * 100.0, 2) if total_requests > 0 else 0.0

        total_input_tokens = sum(log.input_tokens or 0 for log in logs)
        total_output_tokens = sum(log.output_tokens or 0 for log in logs)
        total_tokens_processed = total_input_tokens + total_output_tokens

        # Tokens saved are tokens on cache hits (EXACT_HIT or L2_HIT)
        input_tokens_saved = sum(log.input_tokens or 0 for log in logs if log.cache_status in ("EXACT_HIT", "L2_HIT"))
        output_tokens_saved = sum(log.output_tokens or 0 for log in logs if log.cache_status in ("EXACT_HIT", "L2_HIT"))
        tokens_saved = input_tokens_saved + output_tokens_saved

        # Cost Accounting
        estimated_cost_spent_usd = 0.0
        estimated_cost_saved_usd = 0.0

        for log in logs:
            in_tok = log.input_tokens or 0
            out_tok = log.output_tokens or 0
            model = log.requested_model or "gpt-4o"

            if log.cache_status in ("EXACT_HIT", "L2_HIT"):
                estimated_cost_saved_usd += PricingEngine.calculate_savings(model, in_tok, out_tok)
            elif log.upstream_called:
                estimated_cost_spent_usd += PricingEngine.calculate_cost(model, in_tok, out_tok)

        estimated_cost_spent_usd = round(estimated_cost_spent_usd, 4)
        estimated_cost_saved_usd = round(estimated_cost_saved_usd, 4)
        total_potential_cost = estimated_cost_spent_usd + estimated_cost_saved_usd
        net_savings_pct = (
            round((estimated_cost_saved_usd / total_potential_cost) * 100.0, 2)
            if total_potential_cost > 0
            else 0.0
        )

        # Latency Percentiles & Averages
        gateway_latencies = sorted(log.gateway_latency_ms for log in logs)
        upstream_latencies = [log.upstream_latency_ms for log in logs if log.upstream_latency_ms is not None]
        cache_lookup_latencies = [log.exact_cache_lookup_ms for log in logs if log.exact_cache_lookup_ms is not None]

        p50 = self._calculate_percentile(gateway_latencies, 50)
        p90 = self._calculate_percentile(gateway_latencies, 90)
        p95 = self._calculate_percentile(gateway_latencies, 95)
        p99 = self._calculate_percentile(gateway_latencies, 99)

        avg_gateway = round(sum(gateway_latencies) / len(gateway_latencies), 2) if gateway_latencies else 0.0
        avg_upstream = round(sum(upstream_latencies) / len(upstream_latencies), 2) if upstream_latencies else 0.0
        avg_cache = round(sum(cache_lookup_latencies) / len(cache_lookup_latencies), 2) if cache_lookup_latencies else 0.0

        # Estimated Time Saved: for each hit, time saved is (avg_upstream - cache_latency)
        # or if upstream_latency is known, use default upstream baseline (1200ms) minus lookup time
        time_saved_ms = 0.0
        baseline_upstream_ms = avg_upstream if avg_upstream > 0 else 1200.0
        for log in logs:
            if log.cache_status in ("EXACT_HIT", "L2_HIT"):
                saved_ms = max(0.0, baseline_upstream_ms - (log.gateway_latency_ms or 1.0))
                time_saved_ms += saved_ms

        time_saved_seconds = round(time_saved_ms / 1000.0, 2)

        return AnalyticsOverview(
            total_requests=total_requests,
            exact_hits=exact_hits,
            semantic_hits=semantic_hits,
            total_hits=total_hits,
            misses=misses,
            errors=errors,
            hit_rate_pct=hit_rate_pct,
            total_tokens_processed=total_tokens_processed,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            tokens_saved=tokens_saved,
            input_tokens_saved=input_tokens_saved,
            output_tokens_saved=output_tokens_saved,
            estimated_cost_spent_usd=estimated_cost_spent_usd,
            estimated_cost_saved_usd=estimated_cost_saved_usd,
            net_savings_pct=net_savings_pct,
            latency_p50_ms=p50,
            latency_p90_ms=p90,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            avg_gateway_latency_ms=avg_gateway,
            avg_upstream_latency_ms=avg_upstream,
            avg_cache_lookup_ms=avg_cache,
            time_saved_seconds=time_saved_seconds,
        )

    async def get_timeseries(
        self,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
        points: int = 24,
    ) -> List[TimeseriesPoint]:
        """
        Generates timeseries data points grouped into regular time intervals.
        """
        stmt = select(RequestLog).order_by(RequestLog.created_at.asc())

        if tenant_id:
            stmt = stmt.where(RequestLog.tenant_id == tenant_id)
        if project_id:
            stmt = stmt.where(RequestLog.project_id == project_id)

        result = await self.session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            # Return empty skeleton buckets
            now = datetime.now(timezone.utc)
            return [
                TimeseriesPoint(
                    timestamp=(now - timedelta(hours=points - i)).strftime("%H:%M"),
                    total_requests=0,
                )
                for i in range(points)
            ]

        # Group logs by hour or minute
        now = datetime.now(timezone.utc)
        earliest = logs[0].created_at if logs else now - timedelta(hours=24)
        if earliest.tzinfo is None:
            earliest = earliest.replace(tzinfo=timezone.utc)

        span_seconds = max((now - earliest).total_seconds(), 3600.0)
        bucket_size_seconds = span_seconds / points

        bucket_dict: Dict[int, List[RequestLog]] = {i: [] for i in range(points)}

        for log in logs:
            log_time = log.created_at
            if log_time.tzinfo is None:
                log_time = log_time.replace(tzinfo=timezone.utc)

            offset_sec = (log_time - earliest).total_seconds()
            bucket_idx = min(int(offset_sec / bucket_size_seconds), points - 1)
            if bucket_idx >= 0:
                bucket_dict[bucket_idx].append(log)

        series: List[TimeseriesPoint] = []
        for i in range(points):
            bucket_logs = bucket_dict[i]
            bucket_time = earliest + timedelta(seconds=i * bucket_size_seconds)
            time_label = bucket_time.strftime("%m-%d %H:%M") if span_seconds > 86400 else bucket_time.strftime("%H:%M")

            reqs = len(bucket_logs)
            e_hits = sum(1 for l in bucket_logs if l.cache_status == "EXACT_HIT")
            s_hits = sum(1 for l in bucket_logs if l.cache_status == "L2_HIT")
            misses = sum(1 for l in bucket_logs if l.cache_status == "MISS")
            hits = e_hits + s_hits
            hit_rate = round((hits / reqs) * 100.0, 2) if reqs > 0 else 0.0

            tok_saved = sum(
                (l.input_tokens or 0) + (l.output_tokens or 0)
                for l in bucket_logs
                if l.cache_status in ("EXACT_HIT", "L2_HIT")
            )

            cost_saved = sum(
                PricingEngine.calculate_savings(
                    l.requested_model or "gpt-4o",
                    l.input_tokens or 0,
                    l.output_tokens or 0,
                )
                for l in bucket_logs
                if l.cache_status in ("EXACT_HIT", "L2_HIT")
            )

            latencies = [l.gateway_latency_ms for l in bucket_logs]
            avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

            series.append(
                TimeseriesPoint(
                    timestamp=time_label,
                    total_requests=reqs,
                    exact_hits=e_hits,
                    semantic_hits=s_hits,
                    misses=misses,
                    hit_rate_pct=hit_rate,
                    tokens_saved=tok_saved,
                    cost_saved_usd=round(cost_saved, 4),
                    avg_latency_ms=avg_lat,
                )
            )

        return series

    async def get_model_breakdown(
        self,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[ModelUsageMetrics]:
        """
        Computes performance and savings breakdown grouped by model and provider.
        """
        stmt = select(RequestLog)
        if tenant_id:
            stmt = stmt.where(RequestLog.tenant_id == tenant_id)
        if project_id:
            stmt = stmt.where(RequestLog.project_id == project_id)

        result = await self.session.execute(stmt)
        logs = result.scalars().all()

        groups: Dict[Tuple[str, str], List[RequestLog]] = {}
        for log in logs:
            key = (log.requested_model or "unknown", log.provider or "unknown")
            if key not in groups:
                groups[key] = []
            groups[key].append(log)

        breakdown: List[ModelUsageMetrics] = []
        for (model, provider), model_logs in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
            total_reqs = len(model_logs)
            exact_hits = sum(1 for l in model_logs if l.cache_status == "EXACT_HIT")
            semantic_hits = sum(1 for l in model_logs if l.cache_status == "L2_HIT")
            total_hits = exact_hits + semantic_hits
            misses = sum(1 for l in model_logs if l.cache_status == "MISS")
            hit_rate = round((total_hits / total_reqs) * 100.0, 2) if total_reqs > 0 else 0.0

            tokens_saved = sum(
                (l.input_tokens or 0) + (l.output_tokens or 0)
                for l in model_logs
                if l.cache_status in ("EXACT_HIT", "L2_HIT")
            )

            cost_saved = sum(
                PricingEngine.calculate_savings(
                    model,
                    l.input_tokens or 0,
                    l.output_tokens or 0,
                )
                for l in model_logs
                if l.cache_status in ("EXACT_HIT", "L2_HIT")
            )

            cost_spent = sum(
                PricingEngine.calculate_cost(
                    model,
                    l.input_tokens or 0,
                    l.output_tokens or 0,
                )
                for l in model_logs
                if l.upstream_called
            )

            latencies = [l.gateway_latency_ms for l in model_logs]
            avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

            breakdown.append(
                ModelUsageMetrics(
                    model=model,
                    provider=provider,
                    total_requests=total_reqs,
                    exact_hits=exact_hits,
                    semantic_hits=semantic_hits,
                    misses=misses,
                    hit_rate_pct=hit_rate,
                    tokens_saved=tokens_saved,
                    cost_saved_usd=round(cost_saved, 4),
                    cost_spent_usd=round(cost_spent, 4),
                    avg_latency_ms=avg_lat,
                )
            )

        return breakdown

    async def get_logs(
        self,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
        cache_status: Optional[str] = None,
        model: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> PaginatedLogsResponse:
        """
        Fetches paginated request logs with filtering.
        """
        page = max(1, page)
        limit = min(max(1, limit), 200)
        offset = (page - 1) * limit

        base_stmt = select(RequestLog)
        count_stmt = select(func.count(RequestLog.id))

        if tenant_id:
            base_stmt = base_stmt.where(RequestLog.tenant_id == tenant_id)
            count_stmt = count_stmt.where(RequestLog.tenant_id == tenant_id)
        if project_id:
            base_stmt = base_stmt.where(RequestLog.project_id == project_id)
            count_stmt = count_stmt.where(RequestLog.project_id == project_id)
        if cache_status:
            base_stmt = base_stmt.where(RequestLog.cache_status == cache_status)
            count_stmt = count_stmt.where(RequestLog.cache_status == cache_status)
        if model:
            base_stmt = base_stmt.where(RequestLog.requested_model == model)
            count_stmt = count_stmt.where(RequestLog.requested_model == model)
        if search:
            search_filter = RequestLog.request_id.contains(search) | RequestLog.exact_request_hash.contains(search)
            base_stmt = base_stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total_count = (await self.session.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

        query = base_stmt.order_by(desc(RequestLog.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(query)
        logs = result.scalars().all()

        items: List[RequestLogItem] = []
        for log in logs:
            model_name = log.requested_model or "gpt-4o"
            in_tok = log.input_tokens or 0
            out_tok = log.output_tokens or 0

            cost_spent = (
                PricingEngine.calculate_cost(model_name, in_tok, out_tok)
                if log.upstream_called
                else 0.0
            )
            cost_saved = (
                PricingEngine.calculate_savings(model_name, in_tok, out_tok)
                if log.cache_status in ("EXACT_HIT", "L2_HIT")
                else 0.0
            )

            items.append(
                RequestLogItem(
                    id=log.id,
                    request_id=log.request_id,
                    tenant_id=log.tenant_id,
                    project_id=log.project_id,
                    provider=log.provider,
                    requested_model=log.requested_model,
                    actual_model=log.actual_model,
                    cache_status=log.cache_status,
                    exact_request_hash=log.exact_request_hash,
                    similarity_score=log.similarity_score,
                    guardrail_status=log.guardrail_status,
                    guardrail_failed_check=log.guardrail_failed_check,
                    gateway_latency_ms=round(log.gateway_latency_ms, 2),
                    upstream_latency_ms=round(log.upstream_latency_ms, 2) if log.upstream_latency_ms is not None else None,
                    exact_cache_lookup_ms=round(log.exact_cache_lookup_ms, 2),
                    upstream_called=log.upstream_called,
                    input_tokens=log.input_tokens,
                    output_tokens=log.output_tokens,
                    estimated_cost_usd=cost_spent,
                    estimated_saved_usd=cost_saved,
                    created_at=log.created_at,
                )
            )

        return PaginatedLogsResponse(
            items=items,
            total=total_count,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    def _calculate_percentile(self, sorted_values: List[float], percentile: int) -> float:
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(sorted_values[int(k)], 2)
        d0 = sorted_values[int(f)] * (c - k)
        d1 = sorted_values[int(c)] * (k - f)
        return round(d0 + d1, 2)
