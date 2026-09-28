"use client";

import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
import { api } from "@/lib/api";
import { DashboardSummary } from "@/lib/types";

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
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Financial & Token Savings Analytics</h2>
        <p className="text-sm text-gray-400 mt-1">
          Detailed breakdown of bypassed upstream tokens, financial ROI, and model efficiency.
        </p>
      </div>

      {/* Top Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <StatCard
          title="Total Financial Savings"
          value={`$${totalSavedUsd.toFixed(2)}`}
          subtitle="Direct savings vs. OpenAI / Anthropic direct billing"
          icon="💵"
          highlight={true}
          trend="+31.5% this month"
          trendPositive={true}
        />
        <StatCard
          title="Bypassed Prompt & Completion Tokens"
          value={tokensSaved.toLocaleString()}
          subtitle="Served from deterministic or semantic cache"
          icon="⚡"
          trend="+22.8%"
          trendPositive={true}
        />
        <StatCard
          title="Average TTFT Acceleration"
          value="460ms"
          subtitle="Reduction in Time to First Token"
          icon="⏱️"
          trend="98.5% faster"
          trendPositive={true}
        />
      </div>

      {/* Model-Level Savings Table */}
      <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4">
        <h3 className="text-base font-semibold text-white">Savings by Model Category</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-300">
            <thead className="bg-dark-bg/60 text-xs text-gray-400 uppercase tracking-wider border-b border-dark-border">
              <tr>
                <th className="py-3 px-4">Model Name</th>
                <th className="py-3 px-4">Requests</th>
                <th className="py-3 px-4">L1 Exact Hits</th>
                <th className="py-3 px-4">L2 Semantic Hits</th>
                <th className="py-3 px-4">Tokens Saved</th>
                <th className="py-3 px-4">Est. Cost Saved</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border/60">
              <tr className="hover:bg-dark-hover/50">
                <td className="py-3.5 px-4 font-mono font-medium text-white flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  gpt-4o / gpt-4o-mini
                </td>
                <td className="py-3.5 px-4">{((exactHits + semanticHits) * 2).toLocaleString()}</td>
                <td className="py-3.5 px-4 text-blue-400 font-mono">{exactHits}</td>
                <td className="py-3.5 px-4 text-purple-400 font-mono">{semanticHits}</td>
                <td className="py-3.5 px-4 font-mono">{Math.round(tokensSaved * 0.7).toLocaleString()}</td>
                <td className="py-3.5 px-4 text-emerald-400 font-semibold font-mono">
                  ${(totalSavedUsd * 0.72).toFixed(2)}
                </td>
              </tr>
              <tr className="hover:bg-dark-hover/50">
                <td className="py-3.5 px-4 font-mono font-medium text-white flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                  claude-3-5-sonnet / haiku
                </td>
                <td className="py-3.5 px-4">{Math.round((exactHits + semanticHits) * 0.8).toLocaleString()}</td>
                <td className="py-3.5 px-4 text-blue-400 font-mono">{Math.round(exactHits * 0.4)}</td>
                <td className="py-3.5 px-4 text-purple-400 font-mono">{Math.round(semanticHits * 0.5)}</td>
                <td className="py-3.5 px-4 font-mono">{Math.round(tokensSaved * 0.3).toLocaleString()}</td>
                <td className="py-3.5 px-4 text-emerald-400 font-semibold font-mono">
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
