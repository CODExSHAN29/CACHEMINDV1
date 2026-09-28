"use client";

import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
import LatencySavingsChart from "@/components/LatencySavingsChart";
import CacheRatioChart from "@/components/CacheRatioChart";
import { api } from "@/lib/api";
import { DashboardSummary } from "@/lib/types";

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
  const avgCachedLatency = summary?.cached_average_latency_ms || 1.8;
  const avgUncachedLatency = summary?.uncached_average_latency_ms || 480.0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">System Overview</h2>
          <p className="text-sm text-gray-400 mt-1">
            Real-time telemetry, cache hit efficiency, and latency reduction metrics.
          </p>
        </div>
        <button
          onClick={fetchSummary}
          className="px-3.5 py-1.5 bg-dark-card hover:bg-dark-hover border border-dark-border text-xs text-gray-300 rounded-lg flex items-center gap-2 transition-colors"
        >
          <span className={loading ? "animate-spin" : ""}>🔄</span>
          <span>Refresh</span>
        </button>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Total Inference Requests"
          value={totalRequests.toLocaleString()}
          subtitle="Processed via Gateway"
          icon="⚡"
          trend="+14.2%"
          trendPositive={true}
        />
        <StatCard
          title="Overall Cache Hit Ratio"
          value={`${hitRatio}%`}
          subtitle={`${exactHits} exact + ${semanticHits} semantic`}
          icon="🎯"
          highlight={true}
          trend="+5.8%"
          trendPositive={true}
        />
        <StatCard
          title="Tokens Saved"
          value={tokensSaved}
          subtitle="Direct API bypass"
          icon="🪙"
          trend="+22.4%"
          trendPositive={true}
        />
        <StatCard
          title="Cost Avoided (USD)"
          value={costSaved}
          subtitle="Estimated upstream billing savings"
          icon="💰"
          trend="+18.9%"
          trendPositive={true}
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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

      {/* Quick Status / Engine Details */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-dark-card border border-dark-border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xl">🚀</span>
            <h4 className="text-sm font-semibold text-white">L1 Exact Cache</h4>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            Deterministic SHA-256 fingerprinting with normalized prompt structure. Sub-millisecond lookup.
          </p>
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-gray-500">Latency:</span>
            <span className="text-blue-400 font-semibold">&lt; 1.2ms</span>
          </div>
        </div>

        <div className="bg-dark-card border border-dark-border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xl">🧠</span>
            <h4 className="text-sm font-semibold text-white">L2 Semantic Vector Cache</h4>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            FastEmbed ONNX embeddings (384-dim) with entity & negation guardrails and pgvector indexing.
          </p>
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-gray-500">Similarity Threshold:</span>
            <span className="text-purple-400 font-semibold">&gt; 0.92 Cosine</span>
          </div>
        </div>

        <div className="bg-dark-card border border-dark-border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xl">🛡️</span>
            <h4 className="text-sm font-semibold text-white">PII Sanitization Gateway</h4>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            Inline redaction for Credit Cards (Luhn validated), SSNs, Emails, API Keys, and IPs before caching.
          </p>
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-gray-500">Mode:</span>
            <span className="text-emerald-400 font-semibold">Active Masking</span>
          </div>
        </div>
      </div>
    </div>
  );
}
