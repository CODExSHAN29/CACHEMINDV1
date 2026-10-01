"use client";
import { useState } from "react";
import { RefreshCw } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { DataState, MetricBand, PathDistribution, RequestTable } from "@/components/Telemetry";
import { api } from "@/lib/api";
import { useScopedData } from "@/lib/useScopedData";
export default function DashboardPage() {
  const [refresh, setRefresh] = useState(0);
  const overview = useScopedData(api.getOverview, refresh);
  const logs = useScopedData(api.getRequestLogs, refresh);
  return <div><PageHeader index="01 / Overview" title="Gateway Overview" description="Measured request traffic, memory reuse, and cost avoidance for the selected scope." action={<button className="btn-secondary" aria-label="Refresh telemetry" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={14} />Refresh</button>} />{overview.loading || overview.error || !overview.data ? <DataState loading={overview.loading} error={overview.error} retry={() => setRefresh(v => v + 1)} /> : <><MetricBand data={overview.data} />{!overview.data.total_requests && <div className="hairline-panel mb-6"><DataState empty /></div>}<PathDistribution data={overview.data} /></>}<section className="hairline-panel mt-6"><div className="panel-heading">Recent request activity<span className="text-on-surface-faint">Latest 20 / audit trail</span></div>{logs.loading || logs.error ? <DataState loading={logs.loading} error={logs.error} retry={() => setRefresh(v => v + 1)} /> : logs.data?.items.length ? <RequestTable rows={logs.data.items} /> : <div className="state-panel"><h3>NO RECENT REQUESTS</h3><p>Request events appear here after the gateway handles traffic.</p></div>}</section></div>;
}
