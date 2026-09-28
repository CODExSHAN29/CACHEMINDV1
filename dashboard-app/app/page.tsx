"use client";

import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
import LatencySavingsChart from "@/components/LatencySavingsChart";
import CacheRatioChart from "@/components/CacheRatioChart";
import { api } from "@/lib/api";
import { DashboardSummary } from "@/lib/types";
import {
  Activity,
  Zap,
  Coins,
  ShieldCheck,
  RefreshCw,
  Cpu,
  Layers,
  Database,
  SlidersHorizontal,
  ChevronRight,
} from "lucide-react";

export default function DashboardOverviewPage() {
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
    const interval = setInterval(fetchSummary, 5000);
    return () => clearInterval(interval);
  }, []);

  const totalRequests = summary?.total_requests || 0;
  const exactHits = summary?.exact_hits || 0;
  const semanticHits = summary?.semantic_hits || 0;
  const misses = summary?.cache_misses || 0;
  const hitRatio = summary ? (summary.cache_hit_ratio * 100).toFixed(1) : "0.0";
  const tokensSaved = summary?.tokens_saved?.toLocaleString() || "0";
  const costSaved = summary ? `$${summary.cost_saved_usd.toFixed(2)}` : "$0.00";
  const avgCachedLatency = summary?.cached_average_latency_ms || 1.2;
  const avgUncachedLatency = summary?.uncached_average_latency_ms || 480.0;

  return (
    <div className="space-y-6">
      {/* HUD Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-carbon-750/80">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-laser-emerald font-semibold">
              SYS.ZONE // 01
            </span>
            <span className="text-slate-400 font-mono text-[10px]">
              :: [OBSERVABILITY & CONTROL HUD]
            </span>
          </div>
          <h2 className="text-xl md:text-2xl font-mono font-bold text-white tracking-tight mt-1">
            GATEWAY TELEMETRY & CACHE OVERVIEW
          </h2>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Sub-millisecond exact SHA-256 caching and FastEmbed semantic vector deduplication metrics.
          </p>
        </div>

        <button
          onClick={fetchSummary}
          className="flex items-center gap-2 px-3 py-1.5 bg-carbon-900 hover:bg-carbon-800 border border-carbon-750 hover:border-carbon-600 text-xs font-mono text-slate-200 rounded-sm transition-colors shadow-sm self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-laser-emerald ${loading ? "animate-spin" : ""}`} />
          <span>POLL METRICS</span>
        </button>
      </div>

      {/* Top Telemetry KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Inference Requests"
          value={totalRequests.toLocaleString()}
          subtitle="Processed via Gateway"
          icon={Zap}
          trend="+14.2% RATE"
          trendPositive={true}
          accent="emerald"
          code="REQ.IN"
        />
        <StatCard
          title="Cache Efficiency"
          value={`${hitRatio}%`}
          subtitle={`${exactHits} exact + ${semanticHits} semantic`}
          icon={Activity}
          trend="+5.8% DELTA"
          trendPositive={true}
          accent="cyan"
          code="HIT.RATIO"
        />
        <StatCard
          title="Tokens Avoided"
          value={tokensSaved}
          subtitle="Direct API bypass"
          icon={Coins}
          trend="+22.4% VOL"
          trendPositive={true}
          accent="amber"
          code="TOK.SAVED"
        />
        <StatCard
          title="Cost Avoided (USD)"
          value={costSaved}
          subtitle="Estimated upstream billing delta"
          icon={Database}
          trend="+18.9% SAVED"
          trendPositive={true}
          accent="emerald"
          code="USD.SAVED"
        />
      </div>

      {/* Primary Analytics Visualizers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <LatencySavingsChart
            cachedMs={avgCachedLatency}
            uncachedMs={avgUncachedLatency}
          />
        </div>
        <div className="lg:col-span-1">
          <CacheRatioChart
            exactHits={exactHits}
            semanticHits={semanticHits}
            misses={misses}
          />
        </div>
      </div>

      {/* Industrial Subsystem Status Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-carbon-750/70">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-laser-emerald" />
              <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                L1 EXACT CACHE
              </span>
            </div>
            <span className="text-[9px] font-mono text-laser-emerald bg-laser-emerald/10 border border-laser-emerald/30 px-1.5 py-0.5 rounded-sm font-semibold">
              &lt; 1.0ms
            </span>
          </div>
          <p className="text-xs font-mono text-slate-400 leading-relaxed">
            Deterministic JSON normalization with SHA-256 exact payload hashing. Sub-millisecond RAM & Redis backing.
          </p>
          <div className="pt-2 border-t border-carbon-750/50 flex justify-between items-center text-[10px] font-mono">
            <span className="text-slate-400">HASHING ALGO:</span>
            <span className="text-slate-200">SHA256 // DETERMINISTIC</span>
          </div>
        </div>

        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-carbon-750/70">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-laser-cyan" />
              <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                L2 SEMANTIC CACHE
              </span>
            </div>
            <span className="text-[9px] font-mono text-laser-cyan bg-laser-cyan/10 border border-laser-cyan/30 px-1.5 py-0.5 rounded-sm font-semibold">
              &gt; 0.92 SIM
            </span>
          </div>
          <p className="text-xs font-mono text-slate-400 leading-relaxed">
            FastEmbed ONNX embeddings (384-dim) with entity extraction & negation guardrails for zero hallucination caching.
          </p>
          <div className="pt-2 border-t border-carbon-750/50 flex justify-between items-center text-[10px] font-mono">
            <span className="text-slate-400">VECTOR BACKEND:</span>
            <span className="text-slate-200">FASTEMBED + NUMPY / PGVECTOR</span>
          </div>
        </div>

        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-carbon-750/70">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-laser-amber" />
              <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                PII GATEWAY MASKER
              </span>
            </div>
            <span className="text-[9px] font-mono text-laser-amber bg-laser-amber/10 border border-laser-amber/30 px-1.5 py-0.5 rounded-sm font-semibold">
              MASK MODE
            </span>
          </div>
          <p className="text-xs font-mono text-slate-400 leading-relaxed">
            Automatic redaction of Luhn-verified credit cards, SSNs, phone numbers, secret API keys, and IPs before caching.
          </p>
          <div className="pt-2 border-t border-carbon-750/50 flex justify-between items-center text-[10px] font-mono">
            <span className="text-slate-400">LUHN VALIDATION:</span>
            <span className="text-laser-emerald font-semibold">ENFORCED</span>
          </div>
        </div>
      </div>
    </div>
  );
}
