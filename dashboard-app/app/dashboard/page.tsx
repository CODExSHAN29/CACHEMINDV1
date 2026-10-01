"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { DashboardSummary } from "@/lib/types";
import {
  LayoutDashboard,
  Cpu,
  Zap,
  Activity,
  KeyRound,
  ArrowUpRight,
  ShieldCheck,
  Banknote,
  Clock,
  TrendingUp,
  Layers,
  RefreshCw,
  FolderGit2,
  AlertCircle,
  Database,
} from "lucide-react";

export default function DashboardPage() {
  const { activeWorkspace, activeProject, projects, switchProject } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [hover, setHover] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    if (!activeWorkspace?.id) return;
    setLoading(true);
    try {
      const data = await api.getDashboardSummary(activeWorkspace.id);
      setSummary(data);
    } catch (e) {
      console.error("Failed to load dashboard summary:", e);
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const hitRate = summary
    ? summary.total_requests > 0
      ? ((summary.exact_hits + summary.semantic_hits) / summary.total_requests) * 100
      : (summary.cache_hit_ratio || 0) * 100
    : 0;

  const totalRequests = summary?.total_requests || 0;
  const costSaved = summary?.cost_saved_usd || 0;
  const tokensSaved = summary?.tokens_saved || 0;
  const avgLatency = summary?.cached_average_latency_ms || summary?.average_latency_ms || 1.18;

  const modules = [
    {
      title: "Cache Hit Rate",
      val: `${hitRate.toFixed(1)}%`,
      sub: "L1 Exact + L2 Vector Hits",
      delta: totalRequests > 0 ? `${totalRequests} Total Inferences` : "Awaiting first query",
      color: "text-emerald-400",
      icon: ShieldCheck,
    },
    {
      title: "Avg Cached Latency",
      val: `${avgLatency.toFixed(2)}ms`,
      sub: "P99 < 2.0ms Target",
      delta: summary?.latency_reduction_percent ? `${summary.latency_reduction_percent.toFixed(1)}% vs Upstream` : "Sub-millisecond TTFT",
      color: "text-cyan-400",
      icon: Zap,
    },
    {
      title: "Tokens Bypassed",
      val: tokensSaved.toLocaleString(),
      sub: "Upstream Generation Saved",
      delta: "Exact SHA + 384D Vector",
      color: "text-amber-400",
      icon: TrendingUp,
    },
    {
      title: "Financial ROI",
      val: `$${costSaved.toFixed(2)}`,
      sub: "Direct LLM Spend Avoided",
      delta: "Billed at standard provider rates",
      color: "text-indigo-400",
      icon: Banknote,
    },
    {
      title: "Active Projects",
      val: `${projects.length}`,
      sub: `Current: ${activeProject?.name || "Default"}`,
      delta: activeWorkspace?.name || "Production Tenant",
      color: "text-rose-400",
      icon: KeyRound,
    },
  ];

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-200 font-mono selection:bg-indigo-500/30 pb-20">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-[#07090e]/90 border-b border-slate-800/60 backdrop-blur-2xl px-6 sm:px-8 py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] text-indigo-400 tracking-widest uppercase font-semibold">
              TENANT: {activeWorkspace?.name || activeWorkspace?.id || "AUTHENTICATING..."}
            </span>
          </div>
          <h1 className="font-display font-bold text-2xl text-slate-100 tracking-tight">
            Operations Command Center
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {projects.length > 1 && (
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs">
              <FolderGit2 className="w-3.5 h-3.5 text-indigo-400" />
              <select
                value={activeProject?.id || ""}
                onChange={(e) => switchProject(e.target.value)}
                aria-label="Active Project"
                className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-slate-950 text-slate-200">
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <Link
            href="/cache"
            className="text-xs bg-indigo-950/60 border border-indigo-700/50 px-3 py-1.5 hover:bg-indigo-900/60 transition-colors text-indigo-300"
          >
            PURGE CACHE
          </Link>
          <Link
            href="/cache"
            className="text-xs bg-emerald-950/60 border border-emerald-700/50 px-3 py-1.5 hover:bg-emerald-900/60 transition-colors text-emerald-300"
          >
            WARM CACHE
          </Link>
          <button
            onClick={fetchSummary}
            className="p-1.5 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
            title="Refresh Telemetry"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-400" : ""}`} />
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 sm:px-8 py-8 space-y-10">
        {/* Module Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {modules.map((m) => (
            <div
              key={m.title}
              onMouseEnter={() => setHover(m.title)}
              onMouseLeave={() => setHover(null)}
              className={`text-left relative bg-slate-950/80 border border-slate-800 p-5 transition-all hover:border-indigo-500/40 hover:-translate-y-0.5 shadow-xl ${
                hover === m.title ? "shadow-indigo-900/20" : ""
              }`}
            >
              <div className="flex items-start justify-between mb-4">
                <m.icon className={`w-7 h-7 ${m.color}`} />
                <ArrowUpRight className="w-3.5 h-3.5 text-slate-600" />
              </div>
              <div className={`text-2xl font-display font-bold ${m.color} mb-1 tracking-tight`}>
                {loading ? "..." : m.val}
              </div>
              <div className="text-[11px] text-slate-300 mb-0.5">{m.sub}</div>
              <div className="text-[10px] font-mono text-slate-500">{m.delta}</div>
            </div>
          ))}
        </section>

        {/* Live Query Stream / Activity HUD */}
        <section className="border border-slate-800 bg-slate-950/60 backdrop-blur-md shadow-2xl">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/60 bg-slate-900/30">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <h2 className="font-display font-bold text-lg text-slate-100">Live Inference Status</h2>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">
              TENANT: {activeWorkspace?.id || "default"} | ENGINE: FastEmbed ONNX 384D
            </span>
          </div>

          {totalRequests === 0 ? (
            <div className="p-12 text-center space-y-4">
              <Database className="w-10 h-10 text-indigo-400 mx-auto opacity-70 animate-pulse" />
              <div className="space-y-1">
                <h3 className="font-display font-bold text-base text-slate-200">
                  Ready to Accelerate LLM Traffic
                </h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  No inference requests recorded yet for workspace{" "}
                  <span className="text-indigo-300">{activeWorkspace?.name || activeWorkspace?.id}</span>.
                  Test queries in the interactive playground or initialize the CacheMind SDK.
                </p>
              </div>
              <div className="flex items-center justify-center gap-3 pt-2">
                <Link
                  href="/playground"
                  className="btn-primary text-xs font-mono px-4 py-2 flex items-center gap-2"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>LAUNCH PLAYGROUND</span>
                </Link>
                <Link
                  href="/keys"
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-mono text-slate-300 transition-colors"
                >
                  CREATE API KEY
                </Link>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px] font-mono text-slate-300">
                <thead className="text-slate-500 bg-slate-900/50 border-b border-slate-800">
                  <tr>
                    {["METRIC", "EXACT HITS (L1)", "SEMANTIC HITS (L2)", "MISSES (UPSTREAM)", "TOKENS SAVED", "COST SAVED"].map(
                      (h) => (
                        <th key={h} className="text-left px-5 py-3 font-bold tracking-widest">
                          {h}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-slate-800/40 hover:bg-slate-900/40 transition-colors">
                    <td className="px-5 py-3 text-indigo-300 font-bold">Lifetime Partition</td>
                    <td className="px-5 py-3 text-emerald-400 font-bold tabular-nums">
                      {(summary?.exact_hits || 0).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-cyan-400 font-bold tabular-nums">
                      {(summary?.semantic_hits || 0).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-rose-400 tabular-nums">
                      {(summary?.cache_misses || 0).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-amber-400 tabular-nums">
                      {(summary?.tokens_saved || 0).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-emerald-400 font-bold tabular-nums">
                      ${(summary?.cost_saved_usd || 0).toFixed(4)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Charts & Diagnostics Grid */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="border border-slate-800 bg-slate-950/60 p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
              <Zap className="w-5 h-5 text-indigo-400" />
              <h3 className="font-display font-bold text-lg text-slate-100">
                Cache Hit Ratio Breakdown
              </h3>
            </div>
            <div className="grid grid-cols-3 gap-3 pt-2">
              <div className="bg-slate-900/80 border border-slate-800 p-3">
                <span className="text-[10px] text-slate-400 block mb-1">EXACT L1 HITS</span>
                <span className="text-xl font-bold text-emerald-400 tabular-nums">
                  {(summary?.exact_hits || 0).toLocaleString()}
                </span>
              </div>
              <div className="bg-slate-900/80 border border-slate-800 p-3">
                <span className="text-[10px] text-slate-400 block mb-1">SEMANTIC L2 HITS</span>
                <span className="text-xl font-bold text-cyan-400 tabular-nums">
                  {(summary?.semantic_hits || 0).toLocaleString()}
                </span>
              </div>
              <div className="bg-slate-900/80 border border-slate-800 p-3">
                <span className="text-[10px] text-slate-400 block mb-1">UPSTREAM MISSES</span>
                <span className="text-xl font-bold text-rose-400 tabular-nums">
                  {(summary?.cache_misses || 0).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          <div className="border border-slate-800 bg-slate-950/60 p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
              <Clock className="w-5 h-5 text-cyan-400" />
              <h3 className="font-display font-bold text-lg text-slate-100">
                Latency Reduction Comparison
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="bg-slate-900/80 border border-emerald-900/50 p-4">
                <span className="text-[10px] text-emerald-400 block mb-1 font-bold">CACHEMIND GATEWAY</span>
                <span className="text-2xl font-bold text-emerald-300 tabular-nums">
                  {(summary?.cached_average_latency_ms || 1.18).toFixed(2)}ms
                </span>
                <span className="text-[10px] text-slate-500 block mt-1">Direct memory & vector return</span>
              </div>
              <div className="bg-slate-900/80 border border-rose-900/50 p-4">
                <span className="text-[10px] text-rose-400 block mb-1 font-bold">DIRECT UPSTREAM LLM</span>
                <span className="text-2xl font-bold text-rose-300 tabular-nums">
                  {(summary?.uncached_average_latency_ms || 1200.0).toFixed(0)}ms
                </span>
                <span className="text-[10px] text-slate-500 block mt-1">Full model forward pass</span>
              </div>
            </div>
          </div>
        </section>

        {/* Quick Operations Navigation */}
        <section>
          <h2 className="font-display font-bold text-xl mb-4 text-slate-100">Control Plane Operations</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                label: "Vector Explorer & Purge",
                desc: "Inspect 384-D embeddings, warm or purge partitions",
                href: "/cache",
                icon: Layers,
                color: "text-indigo-400",
              },
              {
                label: "Inference Playground",
                desc: "Live prompt testing with exact & semantic telemetry",
                href: "/playground",
                icon: Zap,
                color: "text-cyan-400",
              },
              {
                label: "Financial Analytics",
                desc: "Token ROI, cost avoidance & TTFT acceleration",
                href: "/analytics",
                icon: Activity,
                color: "text-amber-400",
              },
              {
                label: "API Keys & Quotas",
                desc: "Scoped project credentials with one-time secrets",
                href: "/keys",
                icon: KeyRound,
                color: "text-rose-400",
              },
            ].map((link) => (
              <Link
                key={link.label}
                href={link.href}
                className="group bg-slate-950/80 border border-slate-800 p-5 hover:border-indigo-500/40 transition-all hover:-translate-y-0.5 shadow-xl"
              >
                <div className="flex items-center justify-between mb-3">
                  <link.icon className={`w-6 h-6 ${link.color}`} />
                  <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-indigo-400 transition-colors" />
                </div>
                <h3 className="font-display font-bold text-base text-slate-100 mb-1">{link.label}</h3>
                <p className="text-[11px] font-mono text-slate-500 leading-relaxed">{link.desc}</p>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
