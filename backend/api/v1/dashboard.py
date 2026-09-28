import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analytics.service import AnalyticsService
from backend.auth.dependencies import get_authenticated_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.db.session import get_db

router = APIRouter(tags=["Dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CacheMind Gateway | Observability Dashboard</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: {
                            50: '#eef2ff',
                            100: '#e0e7ff',
                            400: '#818cf8',
                            500: '#6366f1',
                            600: '#4f46e5',
                            700: '#4338ca',
                            900: '#312e81',
                        },
                        darkbg: '#0f172a',
                        darkcard: '#1e293b',
                        darkborder: '#334155'
                    }
                }
            }
        }
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #f1f5f9; }
        code, pre, .mono { font-family: 'JetBrains Mono', monospace; }
        .badge-exact { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-l2 { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); }
        .badge-miss { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }
        .badge-error { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    </style>
</head>
<body class="min-h-screen flex flex-col antialiased">
    <!-- Header Navigation -->
    <header class="border-b border-darkborder bg-darkcard/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-9 w-9 rounded-lg bg-gradient-to-tr from-brand-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-brand-500/20">
                    <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                </div>
                <div>
                    <span class="text-lg font-bold tracking-tight text-white">Cache<span class="text-brand-400">Mind</span></span>
                    <span class="text-xs ml-2 px-2 py-0.5 rounded-full bg-brand-900/60 text-brand-400 font-medium border border-brand-700/50">v0.1.0 Gateway</span>
                </div>
            </div>

            <!-- Controls & Filters -->
            <div class="flex items-center space-x-3">
                <div class="relative">
                    <input type="password" id="apiKeyInput" placeholder="Bearer API Key (optional)" value="sk-dev-admin-master-key-00000000" class="text-xs bg-darkbg border border-darkborder rounded-md px-3 py-1.5 text-slate-300 focus:outline-none focus:border-brand-500 w-56 mono" />
                </div>
                <button id="refreshBtn" onclick="fetchDashboardData()" class="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow transition-all">
                    <svg id="refreshIcon" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span>Refresh</span>
                </button>
                <div class="flex items-center space-x-1 pl-2 border-l border-darkborder text-xs text-slate-400">
                    <span class="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span id="liveStatus">Live</span>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <!-- Top Metrics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            <!-- Card 1: Total Requests & Hit Rate -->
            <div class="bg-darkcard border border-darkborder rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>Cache Hit Rate</span>
                    <svg class="w-4 h-4 text-brand-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <div class="mt-3 flex items-baseline justify-between">
                    <div class="text-3xl font-bold tracking-tight text-white" id="statHitRate">0.0%</div>
                    <div class="text-xs text-slate-400" id="statTotalReqs">0 requests</div>
                </div>
                <div class="mt-3 pt-3 border-t border-darkborder/60 flex justify-between text-xs text-slate-400">
                    <div>Exact: <span class="text-emerald-400 font-medium" id="statExactHits">0</span></div>
                    <div>Semantic (L2): <span class="text-brand-400 font-medium" id="statL2Hits">0</span></div>
                    <div>Misses: <span class="text-slate-300 font-medium" id="statMisses">0</span></div>
                </div>
            </div>

            <!-- Card 2: Cost Savings -->
            <div class="bg-darkcard border border-darkborder rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>Estimated Cost Saved</span>
                    <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <div class="mt-3 flex items-baseline justify-between">
                    <div class="text-3xl font-bold tracking-tight text-emerald-400" id="statCostSaved">$0.0000</div>
                </div>
                <div class="mt-3 pt-3 border-t border-darkborder/60 flex justify-between text-xs text-slate-400">
                    <div>Upstream Cost: <span class="text-slate-300 font-medium" id="statCostSpent">$0.0000</span></div>
                    <div>Savings %: <span class="text-emerald-400 font-medium" id="statSavingsPct">0.0%</span></div>
                </div>
            </div>

            <!-- Card 3: Tokens Saved -->
            <div class="bg-darkcard border border-darkborder rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>Tokens Saved</span>
                    <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                </div>
                <div class="mt-3 flex items-baseline justify-between">
                    <div class="text-3xl font-bold tracking-tight text-white" id="statTokensSaved">0</div>
                </div>
                <div class="mt-3 pt-3 border-t border-darkborder/60 flex justify-between text-xs text-slate-400">
                    <div>Total Processed: <span class="text-slate-300 font-medium" id="statTokensTotal">0</span></div>
                    <div>Saved %: <span class="text-amber-400 font-medium" id="statTokensSavedPct">0.0%</span></div>
                </div>
            </div>

            <!-- Card 4: Gateway Latency Percentiles -->
            <div class="bg-darkcard border border-darkborder rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>Gateway Latency</span>
                    <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <div class="mt-3 flex items-baseline justify-between">
                    <div class="text-3xl font-bold tracking-tight text-white" id="statLatP50">0.0 ms <span class="text-xs font-normal text-slate-400">(p50)</span></div>
                    <div class="text-xs text-slate-400" id="statLatP99">p99: 0.0 ms</div>
                </div>
                <div class="mt-3 pt-3 border-t border-darkborder/60 flex justify-between text-xs text-slate-400">
                    <div>p90: <span class="text-slate-300 font-medium" id="statLatP90">0.0 ms</span></div>
                    <div>p95: <span class="text-slate-300 font-medium" id="statLatP95">0.0 ms</span></div>
                    <div>Upstream p50: <span class="text-slate-300 font-medium" id="statUpstreamP50">0.0 ms</span></div>
                </div>
            </div>
        </div>

        <!-- Charts Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Main Timeseries Chart -->
            <div class="lg:col-span-2 bg-darkcard border border-darkborder rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h2 class="text-sm font-semibold text-white">Traffic & Cache Hit Trends</h2>
                        <p class="text-xs text-slate-400">Hourly request breakdown by cache resolution</p>
                    </div>
                </div>
                <div class="h-64">
                    <canvas id="timeseriesChart"></canvas>
                </div>
            </div>

            <!-- Model Breakdown Chart -->
            <div class="bg-darkcard border border-darkborder rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h2 class="text-sm font-semibold text-white">Model Distribution</h2>
                        <p class="text-xs text-slate-400">Requests by requested LLM model</p>
                    </div>
                </div>
                <div class="h-64 flex items-center justify-center">
                    <canvas id="modelsChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Audit Request Logs Table -->
        <div class="bg-darkcard border border-darkborder rounded-xl shadow-sm overflow-hidden">
            <div class="p-5 border-b border-darkborder flex items-center justify-between">
                <div>
                    <h2 class="text-sm font-semibold text-white">Recent Request Audit Logs</h2>
                    <p class="text-xs text-slate-400">Live telemetry stream of LLM inference queries</p>
                </div>
                <div class="text-xs text-slate-400">
                    Showing latest <span id="logCount">0</span> records
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead class="bg-darkbg/50 text-slate-400 uppercase font-medium border-b border-darkborder">
                        <tr>
                            <th class="px-4 py-3">Time</th>
                            <th class="px-4 py-3">Request ID</th>
                            <th class="px-4 py-3">Model</th>
                            <th class="px-4 py-3">Status</th>
                            <th class="px-4 py-3">Similarity</th>
                            <th class="px-4 py-3">Gateway Latency</th>
                            <th class="px-4 py-3">Upstream Latency</th>
                            <th class="px-4 py-3">Tokens (In / Out)</th>
                            <th class="px-4 py-3">Cost Saved</th>
                        </tr>
                    </thead>
                    <tbody id="logsTableBody" class="divide-y divide-darkborder/50 text-slate-300">
                        <tr>
                            <td colspan="9" class="px-4 py-8 text-center text-slate-500">Loading audit records...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-darkborder bg-darkcard/50 py-4 mt-auto">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
            <div>CacheMind Gateway — Safe, Measurable Semantic Caching for Production AI</div>
            <div class="flex space-x-4">
                <a href="/metrics" target="_blank" class="hover:text-brand-400 transition-colors">Prometheus Metrics (/metrics)</a>
                <a href="/docs" target="_blank" class="hover:text-brand-400 transition-colors">Swagger API Docs (/docs)</a>
            </div>
        </div>
    </footer>

    <!-- Dashboard JavaScript Logic -->
    <script>
        let timeseriesChartInstance = null;
        let modelsChartInstance = null;

        function getAuthHeaders() {
            const apiKey = document.getElementById('apiKeyInput').value.trim();
            const headers = { 'Content-Type': 'application/json' };
            if (apiKey) {
                headers['Authorization'] = apiKey.startsWith('Bearer ') ? apiKey : `Bearer ${apiKey}`;
            }
            return headers;
        }

        async function fetchDashboardData() {
            const refreshIcon = document.getElementById('refreshIcon');
            refreshIcon.classList.add('animate-spin');

            try {
                const headers = getAuthHeaders();

                // 1. Fetch Overview KPIs
                const overviewRes = await fetch('/v1/analytics/overview', { headers });
                if (overviewRes.ok) {
                    const overview = await overviewRes.json();
                    renderOverview(overview);
                }

                // 2. Fetch Timeseries
                const timeseriesRes = await fetch('/v1/analytics/timeseries?interval=1h', { headers });
                if (timeseriesRes.ok) {
                    const timeseries = await timeseriesRes.json();
                    renderTimeseries(timeseries);
                }

                // 3. Fetch Models Breakdown
                const modelsRes = await fetch('/v1/analytics/models', { headers });
                if (modelsRes.ok) {
                    const models = await modelsRes.json();
                    renderModels(models);
                }

                // 4. Fetch Logs
                const logsRes = await fetch('/v1/analytics/logs?limit=25', { headers });
                if (logsRes.ok) {
                    const logs = await logsRes.json();
                    renderLogs(logs);
                }

            } catch (err) {
                console.error("Failed to load dashboard data:", err);
            } finally {
                refreshIcon.classList.remove('animate-spin');
            }
        }

        function renderOverview(data) {
            document.getElementById('statHitRate').textContent = `${data.cache_hit_rate_pct.toFixed(1)}%`;
            document.getElementById('statTotalReqs').textContent = `${data.total_requests.toLocaleString()} requests`;
            document.getElementById('statExactHits').textContent = data.exact_hits.toLocaleString();
            document.getElementById('statL2Hits').textContent = data.l2_hits.toLocaleString();
            document.getElementById('statMisses').textContent = data.cache_misses.toLocaleString();

            document.getElementById('statCostSaved').textContent = `$${data.total_cost_saved_usd.toFixed(4)}`;
            document.getElementById('statCostSpent').textContent = `$${data.total_cost_spent_usd.toFixed(4)}`;
            document.getElementById('statSavingsPct').textContent = `${data.cost_savings_pct.toFixed(1)}%`;

            document.getElementById('statTokensSaved').textContent = data.total_tokens_saved.toLocaleString();
            document.getElementById('statTokensTotal').textContent = data.total_tokens_processed.toLocaleString();
            document.getElementById('statTokensSavedPct').textContent = `${data.tokens_saved_pct.toFixed(1)}%`;

            document.getElementById('statLatP50').innerHTML = `${data.latency_gateway_p50_ms.toFixed(1)} ms <span class="text-xs font-normal text-slate-400">(p50)</span>`;
            document.getElementById('statLatP90').textContent = `${data.latency_gateway_p90_ms.toFixed(1)} ms`;
            document.getElementById('statLatP95').textContent = `${data.latency_gateway_p95_ms.toFixed(1)} ms`;
            document.getElementById('statLatP99').textContent = `p99: ${data.latency_gateway_p99_ms.toFixed(1)} ms`;
            document.getElementById('statUpstreamP50').textContent = `${data.latency_upstream_p50_ms.toFixed(1)} ms`;
        }

        function renderTimeseries(points) {
            const labels = points.map(p => {
                const d = new Date(p.timestamp);
                return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            });
            const exactHits = points.map(p => p.exact_hits);
            const l2Hits = points.map(p => p.l2_hits);
            const misses = points.map(p => p.cache_misses);

            const ctx = document.getElementById('timeseriesChart').getContext('2d');

            if (timeseriesChartInstance) {
                timeseriesChartInstance.destroy();
            }

            timeseriesChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels.length ? labels : ['Current'],
                    datasets: [
                        {
                            label: 'Exact Hit (L1)',
                            data: exactHits.length ? exactHits : [0],
                            backgroundColor: '#10b981',
                            borderRadius: 4
                        },
                        {
                            label: 'Semantic Hit (L2)',
                            data: l2Hits.length ? l2Hits : [0],
                            backgroundColor: '#6366f1',
                            borderRadius: 4
                        },
                        {
                            label: 'Miss',
                            data: misses.length ? misses : [0],
                            backgroundColor: '#475569',
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { stacked: true, grid: { color: '#1e293b' }, ticks: { color: '#94a3b8' } },
                        y: { stacked: true, grid: { color: '#1e293b' }, ticks: { color: '#94a3b8' } }
                    },
                    plugins: {
                        legend: { labels: { color: '#cbd5e1', font: { size: 11 } } }
                    }
                }
            });
        }

        function renderModels(models) {
            const labels = models.map(m => m.model);
            const counts = models.map(m => m.total_requests);

            const ctx = document.getElementById('modelsChart').getContext('2d');

            if (modelsChartInstance) {
                modelsChartInstance.destroy();
            }

            modelsChartInstance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels.length ? labels : ['No Data'],
                    datasets: [{
                        data: counts.length ? counts : [1],
                        backgroundColor: ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6', '#64748b'],
                        borderWidth: 2,
                        borderColor: '#1e293b'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#cbd5e1', boxWidth: 12, font: { size: 10 } } }
                    }
                }
            });
        }

        function renderLogs(logs) {
            document.getElementById('logCount').textContent = logs.length;
            const tbody = document.getElementById('logsTableBody');
            if (!logs || logs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" class="px-4 py-8 text-center text-slate-500">No telemetry logs recorded yet.</td></tr>`;
                return;
            }

            tbody.innerHTML = logs.map(log => {
                let badgeClass = 'badge-miss';
                if (log.cache_status === 'EXACT_HIT') badgeClass = 'badge-exact';
                else if (log.cache_status === 'L2_HIT') badgeClass = 'badge-l2';
                else if (log.cache_status === 'ERROR') badgeClass = 'badge-error';

                const timeStr = new Date(log.timestamp).toLocaleTimeString();
                const simStr = log.similarity_score !== null ? `${(log.similarity_score * 100).toFixed(1)}%` : '-';
                const upLatStr = log.upstream_latency_ms !== null ? `${log.upstream_latency_ms.toFixed(1)} ms` : '-';
                const gwLatStr = `${log.gateway_latency_ms.toFixed(1)} ms`;
                const costSavedStr = log.cost_saved_usd > 0 ? `<span class="text-emerald-400">+$${log.cost_saved_usd.toFixed(4)}</span>` : '$0.0000';

                return `
                    <tr class="hover:bg-darkbg/40 transition-colors">
                        <td class="px-4 py-2.5 text-slate-400 mono">${timeStr}</td>
                        <td class="px-4 py-2.5 text-slate-300 mono font-medium" title="${log.request_id}">${log.request_id.slice(0, 8)}...</td>
                        <td class="px-4 py-2.5 text-slate-300">${log.requested_model}</td>
                        <td class="px-4 py-2.5">
                            <span class="px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${badgeClass}">${log.cache_status}</span>
                        </td>
                        <td class="px-4 py-2.5 text-slate-400">${simStr}</td>
                        <td class="px-4 py-2.5 text-slate-300 font-medium">${gwLatStr}</td>
                        <td class="px-4 py-2.5 text-slate-400">${upLatStr}</td>
                        <td class="px-4 py-2.5 text-slate-400 mono">${log.input_tokens || 0} / ${log.output_tokens || 0}</td>
                        <td class="px-4 py-2.5 font-medium">${costSavedStr}</td>
                    </tr>
                `;
            }).join('');
        }

        // Initial fetch and auto-refresh loop every 5 seconds
        window.addEventListener('DOMContentLoaded', () => {
            fetchDashboardData();
            setInterval(fetchDashboardData, 5000);
        });
    </script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    """
    Renders the CacheMind Observability & Analytics Web Dashboard.
    """
    return HTMLResponse(content=DASHBOARD_HTML)


@router.get("/v1/dashboard/summary")
async def get_dashboard_summary(
    tenant_id: str = Query(default="tenant_default"),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns aggregated metrics summary formatted for the Next.js developer dashboard.
    """
    service = AnalyticsService(db)
    overview = await service.get_overview(tenant_id=tenant_id)
    return {
        "total_requests": overview.total_requests,
        "exact_hits": overview.exact_hits,
        "semantic_hits": overview.semantic_hits,
        "cache_misses": overview.misses,
        "cache_hit_ratio": overview.hit_rate_pct,
        "tokens_saved": overview.tokens_saved,
        "cost_saved_usd": overview.estimated_cost_saved_usd,
        "average_latency_ms": overview.avg_gateway_latency_ms,
        "cached_average_latency_ms": overview.avg_cache_lookup_ms,
        "uncached_average_latency_ms": overview.avg_upstream_latency_ms,
        "latency_reduction_percent": overview.net_savings_pct,
    }
