import Link from "next/link";
import { AnalyticsOverview, RequestLog } from "@/lib/types";
export function MetricBand({ data }: { data: AnalyticsOverview }) {
  const observed = data.total_requests > 0;
  const values = [
    ["Total requests", data.total_requests.toLocaleString(), "Observed requests"],
    ["Cache hit rate", observed ? `${data.hit_rate_pct.toFixed(2)}%` : "—", "Exact + semantic"],
    ["Exact hits", data.exact_hits.toLocaleString(), "L1 / fingerprint"],
    ["Semantic hits", data.semantic_hits.toLocaleString(), "L2 / similarity"],
    ["Cache misses", data.misses.toLocaleString(), "Upstream path"],
    ["Tokens saved", data.tokens_saved.toLocaleString(), "Avoided generation"],
    ["Est. cost saved", `$${data.estimated_cost_saved_usd.toFixed(4)}`, "Provider pricing estimate"],
    ["Avg. gateway latency", observed ? `${data.avg_gateway_latency_ms.toFixed(2)} ms` : "—", "Measured gateway time"],
  ];
  return <div className="metric-band">{values.map(([label, value, caption]) => <div key={label} className="metric-cell"><div className="label-caps">{label}</div><div className="metric-value">{value}</div><div className="metric-caption">{caption}</div></div>)}</div>;
}
export function DataState({ loading, error, empty = false, retry }: { loading?: boolean; error?: string; empty?: boolean; retry?: () => void }) {
  return <div className="state-panel" role={error ? "alert" : "status"}><h3>{loading ? "LOADING OBSERVATIONS" : error ? "DATA UNAVAILABLE" : empty ? "NO REQUESTS OBSERVED" : "AWAITING DATA"}</h3><p>{error || (loading ? "Reading telemetry for the selected workspace and project." : "Send your first request through CacheMind to begin collecting telemetry.")}</p>{error && retry && <button className="btn-secondary" onClick={retry}>Retry</button>}{empty && <div className="flex flex-wrap gap-3 mt-2"><Link className="btn-primary" href="/keys">Create API key</Link><a className="btn-secondary" href="/#integration">View integration</a></div>}</div>;
}
export function RequestTable({ rows }: { rows: RequestLog[] }) {
  return <div className="overflow-x-auto"><table className="data-table"><thead className="table-header-row"><tr>{["Timestamp", "Request", "Model", "Cache path", "Similarity", "Latency", "Upstream"].map(label => <th key={label} className="table-header-cell">{label}</th>)}</tr></thead><tbody>{rows.map(row => <tr className="table-row-hover" key={row.request_id}><td>{new Date(row.created_at).toLocaleString()}</td><td title={row.request_id}>{row.request_id.slice(0, 12)}</td><td>{row.actual_model || row.requested_model}</td><td><span className="badge-pill status-badge" data-state={row.cache_status}>{row.cache_status}</span></td><td>{row.similarity_score == null ? "—" : row.similarity_score.toFixed(4)}</td><td>{row.gateway_latency_ms.toFixed(2)} ms</td><td>{row.upstream_called ? "YES" : "NO"}</td></tr>)}</tbody></table></div>;
}
export function PathDistribution({ data }: { data: AnalyticsOverview }) {
  return <section className="hairline-panel"><div className="panel-heading">Request path distribution<span className="text-on-surface-faint">Observed / count</span></div>{[["L1 / EXACT", data.exact_hits], ["L2 / SEMANTIC", data.semantic_hits], ["UPSTREAM / MISS", data.misses]].map(([label, value]) => <div className="path-row" key={label}><span>{label}</span><div className="path-track"><span style={{ width: `${data.total_requests ? Number(value) / data.total_requests * 100 : 0}%` }} /></div><span className="text-right">{Number(value).toLocaleString()}</span></div>)}</section>;
}
