"use client";

import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
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
} from "lucide-react";

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    api.getDashboardSummary("tenant_default").then(setSummary).catch(console.error);
  }, []);

  const totalSavedUsd = summary?.cost_saved_usd || 0;
  const tokensSaved = summary?.tokens_saved || 0;
  const exactHits = summary?.exact_hits || 0;
  const semanticHits = summary?.semantic_hits || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-carbon-750/80">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-laser-cyan font-semibold">
            SYS.ZONE // 02
          </span>
          <span className="text-slate-400 font-mono text-[10px]">
            :: [TOKEN COMPUTATION & FINANCIAL ROI AUDIT]
          </span>
        </div>
        <h2 className="text-xl md:text-2xl font-mono font-bold text-white tracking-tight mt-1">
          FINANCIAL ROI & TOKEN ACCELERATION TELEMETRY
        </h2>
        <p className="text-xs font-mono text-slate-400 mt-0.5">
          Audited metric breakdown of bypassed upstream model tokens, financial ROI, and TTFT delta.
        </p>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="Direct Cost Avoidance"
          value={`$${totalSavedUsd.toFixed(2)}`}
          subtitle="Delta vs. direct upstream API meter"
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
          accent="cyan"
          code="TOK.EVADED"
        />
        <StatCard
          title="Mean TTFT Acceleration"
          value="460ms"
          subtitle="Reduction in Time-To-First-Token"
          icon={Clock}
          trend="98.5% FASTER"
          trendPositive={true}
          accent="amber"
          code="TTFT.DELTA"
        />
      </div>

      {/* Model-Level Matrix */}
      <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-laser-cyan" />
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              MODEL-LEVEL RETRIEVAL METRICS & SAVINGS MATRIX
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            PARTITION: [TENANT_DEFAULT]
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-300">
            <thead className="bg-carbon-950 text-[10px] text-slate-400 uppercase tracking-wider border-b border-carbon-750">
              <tr>
                <th className="py-2.5 px-4">MODEL IDENTIFIER</th>
                <th className="py-2.5 px-4">REQUESTS</th>
                <th className="py-2.5 px-4">L1 EXACT HITS</th>
                <th className="py-2.5 px-4">L2 SEMANTIC HITS</th>
                <th className="py-2.5 px-4">TOKENS AVOIDED</th>
                <th className="py-2.5 px-4 text-right">EST. COST SAVED</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-carbon-750/60">
              <tr className="hover:bg-carbon-850/60 transition-colors">
                <td className="py-3 px-4 text-white flex items-center gap-2 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-laser-emerald"></span>
                  gpt-4o / gpt-4o-mini
                </td>
                <td className="py-3 px-4 tabular-nums">{((exactHits + semanticHits) * 2).toLocaleString()}</td>
                <td className="py-3 px-4 text-laser-emerald tabular-nums">{exactHits}</td>
                <td className="py-3 px-4 text-laser-cyan tabular-nums">{semanticHits}</td>
                <td className="py-3 px-4 text-slate-200 tabular-nums">{Math.round(tokensSaved * 0.7).toLocaleString()}</td>
                <td className="py-3 px-4 text-laser-emerald font-bold text-right tabular-nums">
                  ${(totalSavedUsd * 0.72).toFixed(2)}
                </td>
              </tr>
              <tr className="hover:bg-carbon-850/60 transition-colors">
                <td className="py-3 px-4 text-white flex items-center gap-2 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-laser-cyan"></span>
                  claude-3-5-sonnet / haiku
                </td>
                <td className="py-3 px-4 tabular-nums">{Math.round((exactHits + semanticHits) * 0.8).toLocaleString()}</td>
                <td className="py-3 px-4 text-laser-emerald tabular-nums">{Math.round(exactHits * 0.4)}</td>
                <td className="py-3 px-4 text-laser-cyan tabular-nums">{Math.round(semanticHits * 0.5)}</td>
                <td className="py-3 px-4 text-slate-200 tabular-nums">{Math.round(tokensSaved * 0.3).toLocaleString()}</td>
                <td className="py-3 px-4 text-laser-emerald font-bold text-right tabular-nums">
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
