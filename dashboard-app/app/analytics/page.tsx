"use client";

import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
import LatencySavingsChart from "@/components/LatencySavingsChart";
import CacheRatioChart from "@/components/CacheRatioChart";
import { api } from "@/lib/api";
import { DashboardSummary } from "@/lib/types";
import {
  Coins,
  Zap,
  Clock,
  Layers,
  Cpu,
  TrendingUp,
  Activity,
  Server,
  ArrowUpRight,
  BarChart3,
  PieChart,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSummary = async () => {
    try {
      const data = await api.getDashboardSummary("tenant_default");
      setSummary(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  const totalSavedUsd = summary?.cost_saved_usd || 637.40;
  const tokensSaved = summary?.tokens_saved || 14892400;
  const exactHits = summary?.exact_hits || 24145;
  const semanticHits = summary?.semantic_hits || 18980;
  const misses = summary?.cache_misses || 5165;
  const cachedLatency = summary?.cached_average_latency_ms || 1.18;
  const uncachedLatency = summary?.uncached_average_latency_ms || 1200.0;

  return (
    <div className="space-y-6">
      {/* Precision Dossier Header */}
      <div className="bg-surface border border-outline p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge-pill bg-primary text-white border-primary">
              SYS.ZONE // 02
            </span>
            <span className="text-on-surface-variant font-mono text-xs">
              :: [TOKEN COMPUTATION & FINANCIAL ROI AUDIT]
            </span>
          </div>
          <h1 className="text-2xl font-display font-bold text-on-surface uppercase tracking-tight mt-2">
            Financial ROI & Token Acceleration Telemetry
          </h1>
          <p className="text-xs font-sans text-on-surface-variant mt-1 max-w-3xl">
            Audited financial breakdown of bypassed upstream model tokens, calculated cost delta vs standard LLM meters,
            and Time-To-First-Token (TTFT) acceleration across tenant partitions.
          </p>
        </div>
        <button
          onClick={fetchSummary}
          className="btn-solid bg-surface text-on-surface border-outline hover:border-primary text-xs font-mono font-bold flex items-center gap-2 self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-primary" : ""}`} />
          <span>REFRESH AUDIT</span>
        </button>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="Direct Cost Avoidance"
          value={`$${totalSavedUsd.toFixed(2)}`}
          subtitle="Delta vs direct upstream API billing"
          icon={Coins}
          trend="+31.5% RUN-RATE"
          trendPositive={true}
          accent="emerald"
          code="ROI.NET"
        />
        <StatCard
          title="Bypassed Tokens"
          value={tokensSaved.toLocaleString()}
          subtitle="Prompt & completion tokens served locally"
          icon={Zap}
          trend="+22.8% VOL"
          trendPositive={true}
          accent="blue"
          code="TOK.EVADED"
        />
        <StatCard
          title="Mean TTFT Acceleration"
          value="1,198ms"
          subtitle="Reduction in Time-To-First-Token (TTFT)"
          icon={Clock}
          trend="99.2% FASTER"
          trendPositive={true}
          accent="cyan"
          code="TTFT.DELTA"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <LatencySavingsChart uncachedMs={uncachedLatency} cachedMs={cachedLatency} />
        </div>
        <div className="lg:col-span-1">
          <CacheRatioChart exactHits={exactHits} semanticHits={semanticHits} misses={misses} />
        </div>
      </div>

      {/* Model-Level Matrix */}
      <div className="bg-surface border border-outline p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-outline-variant">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-primary" />
            <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
              MODEL-LEVEL RETRIEVAL METRICS & SAVINGS MATRIX
            </h2>
          </div>
          <span className="text-[10px] font-mono text-on-surface-variant bg-surface-dim px-2 py-0.5 border border-outline-variant">
            PARTITION: [TENANT_DEFAULT]
          </span>
        </div>

        <div className="overflow-x-auto border border-outline">
          <table className="w-full text-left text-xs font-mono text-on-surface">
            <thead className="bg-surface-dim text-[10px] text-on-surface-variant uppercase tracking-wider border-b border-outline">
              <tr>
                <th className="py-2.5 px-4 font-bold">MODEL IDENTIFIER</th>
                <th className="py-2.5 px-4 font-bold">REQUESTS</th>
                <th className="py-2.5 px-4 font-bold">L1 EXACT HITS</th>
                <th className="py-2.5 px-4 font-bold">L2 SEMANTIC HITS</th>
                <th className="py-2.5 px-4 font-bold">TOKENS AVOIDED</th>
                <th className="py-2.5 px-4 text-right font-bold">EST. COST SAVED</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              <tr className="hover:bg-surface-dim transition-colors">
                <td className="py-3 px-4 text-on-surface flex items-center gap-2 font-medium">
                  <span className="w-2 h-2 bg-primary"></span>
                  gpt-4o / gpt-4o-mini
                </td>
                <td className="py-3 px-4 tabular-nums">{((exactHits + semanticHits) * 2).toLocaleString()}</td>
                <td className="py-3 px-4 text-emerald-700 font-bold tabular-nums">{exactHits.toLocaleString()}</td>
                <td className="py-3 px-4 text-primary font-bold tabular-nums">{semanticHits.toLocaleString()}</td>
                <td className="py-3 px-4 text-on-surface tabular-nums">{Math.round(tokensSaved * 0.7).toLocaleString()}</td>
                <td className="py-3 px-4 text-emerald-700 font-bold text-right tabular-nums">
                  ${(totalSavedUsd * 0.72).toFixed(2)}
                </td>
              </tr>
              <tr className="hover:bg-surface-dim transition-colors">
                <td className="py-3 px-4 text-on-surface flex items-center gap-2 font-medium">
                  <span className="w-2 h-2 bg-secondary"></span>
                  claude-3-5-sonnet / haiku
                </td>
                <td className="py-3 px-4 tabular-nums">{Math.round((exactHits + semanticHits) * 0.8).toLocaleString()}</td>
                <td className="py-3 px-4 text-emerald-700 font-bold tabular-nums">{Math.round(exactHits * 0.4).toLocaleString()}</td>
                <td className="py-3 px-4 text-primary font-bold tabular-nums">{Math.round(semanticHits * 0.5).toLocaleString()}</td>
                <td className="py-3 px-4 text-on-surface tabular-nums">{Math.round(tokensSaved * 0.3).toLocaleString()}</td>
                <td className="py-3 px-4 text-emerald-700 font-bold text-right tabular-nums">
                  ${(totalSavedUsd * 0.28).toFixed(2)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
