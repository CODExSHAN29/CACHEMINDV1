"use client";

import React, { useState } from "react";
import { Calculator, DollarSign, Clock, Sparkles, TrendingUp, Cpu, ArrowRight } from "lucide-react";

interface ModelPricing {
  name: string;
  costPer1k: number; // Blended input/output per 1k tokens
  avgLatencyMs: number;
}

const MODELS: Record<string, ModelPricing> = {
  "gpt-4o": { name: "GPT-4o", costPer1k: 0.0075, avgLatencyMs: 950 },
  "claude-3-5-sonnet": { name: "Claude 3.5 Sonnet", costPer1k: 0.009, avgLatencyMs: 1100 },
  "gpt-4o-mini": { name: "GPT-4o mini", costPer1k: 0.0003, avgLatencyMs: 420 },
  "llama-3-70b": { name: "Llama-3 70B (Hosted)", costPer1k: 0.002, avgLatencyMs: 750 },
};

export default function RoiCalculator() {
  const [monthlyRequests, setMonthlyRequests] = useState<number>(500000);
  const [avgTokens, setAvgTokens] = useState<number>(1200);
  const [selectedModel, setSelectedModel] = useState<string>("gpt-4o");
  const [cacheHitRate, setCacheHitRate] = useState<number>(74); // 74% typical semantic hit rate

  const modelInfo = MODELS[selectedModel] || MODELS["gpt-4o"];

  // Monthly without CacheMind
  const unacceleratedCost = (monthlyRequests * avgTokens * modelInfo.costPer1k) / 1000;

  // With CacheMind (Cache hits cost $0.000 in upstream LLM API tokens)
  const cachedRequests = monthlyRequests * (cacheHitRate / 100);
  const savedCost = (cachedRequests * avgTokens * modelInfo.costPer1k) / 1000;
  const annualSavings = savedCost * 12;

  // Latency hours saved: (cached_requests * (avgLatencyMs - 1.2ms)) / (1000 * 3600)
  const latencyMsSavedPerCall = Math.max(10, modelInfo.avgLatencyMs - 1.2);
  const totalHoursSaved = (cachedRequests * latencyMsSavedPerCall) / (1000 * 3600);

  return (
    <div className="w-full bg-slate-950/80 border border-slate-800 p-6 lg:p-10 shadow-2xl backdrop-blur-xl relative overflow-hidden">
      {/* Decorative ambient radial glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="max-w-3xl mb-8">
        <div className="flex items-center gap-2 mb-2">
          <Calculator className="w-4 h-4 text-indigo-400" />
          <span className="label-caps text-indigo-400">ECONOMIC VALUE MODEL</span>
        </div>
        <h3 className="font-display font-bold text-3xl text-slate-100 tracking-tight">
          Enterprise ROI & Compute Savings Calculator
        </h3>
        <p className="text-xs font-mono text-slate-400 mt-2">
          Simulate how much your organization saves per month by intercepting repeat, rephrased, and semantic queries at the gateway.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Controls Column */}
        <div className="lg:col-span-6 space-y-6">
          {/* Model Selector */}
          <div>
            <label className="text-xs font-mono text-slate-300 font-semibold mb-2 block uppercase">
              1. Upstream Base LLM
            </label>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(MODELS).map(([key, val]) => (
                <button
                  key={key}
                  onClick={() => setSelectedModel(key)}
                  className={`p-3 text-left border transition-all text-xs font-mono ${
                    selectedModel === key
                      ? "bg-slate-900 border-indigo-500 text-indigo-300 shadow-[0_0_10px_rgba(99,102,241,0.2)]"
                      : "bg-slate-950/80 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <div className="font-bold text-slate-200">{val.name}</div>
                  <div className="text-[10px] text-slate-500">~{val.avgLatencyMs}ms avg latency</div>
                </button>
              ))}
            </div>
          </div>

          {/* Monthly Requests Slider */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-xs font-mono text-slate-300 font-semibold uppercase">
                2. Monthly Request Volume
              </label>
              <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-950/80 border border-indigo-800/80 px-2 py-0.5">
                {monthlyRequests.toLocaleString()} queries / mo
              </span>
            </div>
            <input
              type="range"
              min={50000}
              max={10000000}
              step={50000}
              value={monthlyRequests}
              onChange={(e) => setMonthlyRequests(Number(e.target.value))}
              className="w-full accent-indigo-500 h-2 bg-slate-800 rounded-none cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
              <span>50k</span>
              <span>1M</span>
              <span>5M</span>
              <span>10M+</span>
            </div>
          </div>

          {/* Avg Tokens per Call */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-xs font-mono text-slate-300 font-semibold uppercase">
                3. Average Tokens per Query
              </label>
              <span className="text-xs font-mono font-bold text-cyan-400 bg-cyan-950/80 border border-cyan-800/80 px-2 py-0.5">
                {avgTokens.toLocaleString()} tokens
              </span>
            </div>
            <input
              type="range"
              min={250}
              max={8000}
              step={250}
              value={avgTokens}
              onChange={(e) => setAvgTokens(Number(e.target.value))}
              className="w-full accent-cyan-500 h-2 bg-slate-800 rounded-none cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
              <span>250</span>
              <span>2,000</span>
              <span>4,000</span>
              <span>8,000</span>
            </div>
          </div>

          {/* Cache Hit Rate */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-xs font-mono text-slate-300 font-semibold uppercase">
                4. Projected Semantic Hit Rate
              </label>
              <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/80 border border-emerald-800/80 px-2 py-0.5">
                {cacheHitRate}% Hit Ratio
              </span>
            </div>
            <input
              type="range"
              min={20}
              max={95}
              step={1}
              value={cacheHitRate}
              onChange={(e) => setCacheHitRate(Number(e.target.value))}
              className="w-full accent-emerald-500 h-2 bg-slate-800 rounded-none cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
              <span>20% (Sparse)</span>
              <span>50% (Standard)</span>
              <span>75% (Agentic Loops)</span>
              <span>95% (High Repetition)</span>
            </div>
          </div>
        </div>

        {/* Results Metrics Output Card */}
        <div className="lg:col-span-6 flex flex-col justify-between bg-gradient-to-br from-slate-900 to-slate-950 border border-indigo-500/40 p-6 lg:p-8 relative shadow-2xl">
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-mono font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                PROJECTED FINANCIAL IMPACT
              </span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 border border-emerald-800 px-2 py-0.5">
                {cacheHitRate}% OF UPSTREAM BILL ELIMINATED
              </span>
            </div>

            {/* Big Headline Savings */}
            <div>
              <div className="text-[11px] font-mono text-slate-400 uppercase mb-1">
                Estimated Monthly Savings
              </div>
              <div className="font-display text-4xl sm:text-5xl font-bold text-emerald-400 tracking-tight">
                ${Math.round(savedCost).toLocaleString()}
                <span className="text-sm font-mono font-normal text-slate-400 ml-2">/ month</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="bg-slate-950 p-4 border border-slate-800">
                <div className="text-[10px] font-mono text-slate-400 mb-1 flex items-center gap-1 uppercase">
                  <DollarSign className="w-3 h-3 text-emerald-400" /> Annual Savings
                </div>
                <div className="font-display text-2xl font-bold text-slate-100">
                  ${Math.round(annualSavings).toLocaleString()}
                </div>
              </div>

              <div className="bg-slate-950 p-4 border border-slate-800">
                <div className="text-[10px] font-mono text-slate-400 mb-1 flex items-center gap-1 uppercase">
                  <Clock className="w-3 h-3 text-cyan-400" /> Latency Reclaimed
                </div>
                <div className="font-display text-2xl font-bold text-cyan-300">
                  {Math.round(totalHoursSaved).toLocaleString()} hrs
                </div>
              </div>
            </div>

            <div className="text-xs font-mono text-slate-300 space-y-2 bg-slate-950/60 p-4 border border-slate-800/80">
              <div className="flex justify-between">
                <span className="text-slate-400">Baseline Direct LLM Cost:</span>
                <span className="text-rose-400 font-semibold">${Math.round(unacceleratedCost).toLocaleString()} / mo</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">New Direct LLM Cost:</span>
                <span className="text-emerald-400 font-semibold">${Math.round(unacceleratedCost - savedCost).toLocaleString()} / mo</span>
              </div>
              <div className="flex justify-between border-t border-slate-800 pt-2 font-bold">
                <span className="text-indigo-400">Monthly Net ROI:</span>
                <span className="text-emerald-400">+{Math.round((savedCost / Math.max(149, savedCost * 0.05)) * 100)}%</span>
              </div>
            </div>
          </div>

          <div className="pt-6">
            <a
              href="#pricing"
              className="btn-primary w-full text-center justify-center py-3 text-xs font-mono flex items-center gap-2"
            >
              DEPLOY CACHEMIND GATEWAY NOW
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
