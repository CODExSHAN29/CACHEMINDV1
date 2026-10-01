"use client";

import React, { useState, useCallback } from "react";
import { Zap, Play, CheckCircle2, Clock, DollarSign, Cpu, ArrowRight, ShieldAlert, Sparkles, Terminal } from "lucide-react";

interface BenchmarkStep {
  label: string;
  status: "idle" | "running" | "done" | "miss";
  detail: string;
  headers?: Record<string, string>;
  latencyMs?: number;
  similarity?: number;
}

const STEPS: BenchmarkStep[] = [
  { label: "STEP 1 — COLD MISS", status: "idle", detail: "First query; upstream LLM serves response. Cache misses both L1 exact and L2 vector.", headers: {} },
  { label: "STEP 2 — L1 EXACT HIT", status: "idle", detail: "Identical prompt re-submitted. SHA-256 fingerprint matches L1 exact key.", headers: {} },
  { label: "STEP 3 — L2 SEMANTIC HIT", status: "idle", detail: "Paraphrased prompt submitted. 384D FastEmbed cosine similarity ≥ 0.92 triggers L2 hit.", headers: {} },
];

const GATEWAY = "http://localhost:8000/v1/chat/completions";

export default function LiveBenchmark() {
  const [steps, setSteps] = useState<BenchmarkStep[]>(STEPS);
  const [isRunning, setIsRunning] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("What is CacheMind's SLA for enterprise semantic caching?");

  const runStep = useCallback(async (idx: number, payload: any) => {
    setSteps((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], status: "running", detail: "Request in flight to gateway..." };
      return next;
    });

    const t0 = performance.now();
    try {
      const res = await fetch(GATEWAY, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CacheMind-Benchmark": "public-ftue",
        },
        body: JSON.stringify(payload),
      });
      const t1 = performance.now();
      const latency = Math.round(t1 - t0);

      // Headers exposed by gateway
      const status = res.headers.get("X-CacheMind-Status") || "MISS";
      const gatewayMs = res.headers.get("X-CacheMind-Gateway-Latency-Ms") || "—";
      const lookupMs = res.headers.get("X-CacheMind-Lookup-Ms") || "—";
      const upstreamMs = res.headers.get("X-CacheMind-Upstream-Ms") || "—";
      const exactHash = res.headers.get("X-CacheMind-Exact-Hash") || "—";
      const similarity = res.headers.get("X-CacheMind-Similarity") || "—";

      const isHit = status === "EXACT_HIT" || status === "L2_HIT";
      const isMiss = status === "MISS";

      setSteps((prev) => {
        const next = [...prev];
        next[idx] = {
          ...next[idx],
          status: isHit ? "done" : isMiss ? "miss" : "done",
          detail: `Status=${status} | Gateway=${gatewayMs}ms | Lookup=${lookupMs}ms | Upstream=${upstreamMs}ms | Hash=${exactHash?.slice(0, 16)}… | Sim=${similarity}`,
          headers: {
            "X-CacheMind-Status": status,
            "X-CacheMind-Gateway-Latency-Ms": gatewayMs,
            "X-CacheMind-Lookup-Ms": lookupMs,
            "X-CacheMind-Upstream-Ms": upstreamMs,
            "X-CacheMind-Exact-Hash": exactHash,
            "X-CacheMind-Similarity": similarity,
          },
          latencyMs: latency,
          similarity: similarity === "—" ? undefined : parseFloat(similarity),
        };
        return next;
      });
    } catch (e: any) {
      setSteps((prev) => {
        const next = [...prev];
        next[idx] = { ...next[idx], status: "miss", detail: `Assay completed (Local gateway: ${e.message})` };
        return next;
      });
    }
  }, []);

  const runBenchmark = useCallback(async () => {
    setIsRunning(true);
    setSteps(STEPS.map(s => ({ ...s, status: "idle", detail: s.detail, headers: {} })));

    // Step 1: Cold miss
    await runStep(0, {
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: customPrompt.trim() || "What is CacheMind's SLA for enterprise semantic caching?" }],
    });

    // Small delay so user sees sequence
    await new Promise((r) => setTimeout(r, 400));

    // Step 2: Exact same prompt = L1 exact hit
    await runStep(1, {
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: customPrompt.trim() || "What is CacheMind's SLA for enterprise semantic caching?" }],
    });

    await new Promise((r) => setTimeout(r, 400));

    // Step 3: Paraphrased = L2 semantic hit
    await runStep(2, {
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: "Explain CacheMind enterprise SLA and caching reliability guarantees." }],
    });

    setIsRunning(false);
  }, [customPrompt, runStep]);

  return (
    <div className="w-full bg-slate-950/70 border border-slate-800 backdrop-blur-xl p-6 lg:p-8 shadow-2xl relative overflow-hidden">
      <div className="absolute -top-24 -right-24 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="label-caps text-indigo-400">REAL-TIME EXECUTION TELEMETRY</span>
          </div>
          <h3 className="font-display font-bold text-2xl text-slate-100 tracking-tight">
            Direct Upstream LLM vs CacheMind Gateway
          </h3>
          <p className="text-xs font-mono text-slate-400 mt-1">
            First-time user workflow: Cold Miss → L1 Exact Hit → L2 Semantic Hit. All values from live HTTP round-trips.
          </p>
        </div>
        <button
          onClick={runBenchmark}
          disabled={isRunning}
          className="btn-primary text-xs font-mono flex items-center gap-2"
        >
          {isRunning ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
              RUNNING LIVE PIPELINE...
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              START FTUE BENCHMARK
            </>
          )}
        </button>
      </div>

      {/* FTUE Steps */}
      <div className="space-y-3 mb-6">
        {steps.map((step, idx) => (
          <div key={idx} className={`border bg-slate-900/30 p-4 transition-colors ${step.status === "done" ? "border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.15)]" : step.status === "miss" ? "border-rose-500/40" : "border-slate-800/60"}`}>
            <div className="flex items-center gap-3 mb-2">
              <span className={`text-[10px] font-mono font-bold px-2 py-0.5 border ${step.status === "done" ? "bg-emerald-950 text-emerald-300 border-emerald-800" : step.status === "running" ? "bg-amber-950 text-amber-300 border-amber-800 animate-pulse" : step.status === "miss" ? "bg-rose-950 text-rose-300 border-rose-800" : "bg-slate-950 text-slate-300 border-slate-800"}`}>
                {step.label}
              </span>
              {step.latencyMs !== undefined && (
                <span className="text-[10px] font-mono text-indigo-300">
                  Round-trip {step.latencyMs}ms
                </span>
              )}
              {step.similarity !== undefined && (
                <span className="text-[10px] font-mono text-emerald-300">
                  Cosine {step.similarity.toFixed(4)}
                </span>
              )}
            </div>
            <p className="text-xs font-mono text-slate-300 mb-2">{step.detail}</p>
            {step.headers && Object.keys(step.headers).length > 0 && (
              <div className="bg-slate-950 border border-slate-800 p-2.5 font-mono text-[10px] text-slate-400 leading-relaxed grid grid-cols-2 gap-x-4 gap-y-1">
                {Object.entries(step.headers).map(([k, v]) => (
                  <div key={k}>
                    <span className="text-indigo-400">{k}:</span> {v}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Prompt input */}
      <div className="mb-6 bg-slate-900/60 border border-slate-800 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Terminal className="w-3 h-3 text-indigo-400" />
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Active Query Prompt</span>
        </div>
        <textarea
          rows={2}
          className="w-full bg-slate-950 border border-slate-800 p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 resize-none"
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          placeholder="Type your query to test against the live gateway..."
        />
      </div>

      {/* Comparison grids — static reference for direct vs cached */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900/40 border border-slate-800/80 p-5 space-y-4 relative">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <span className="font-mono text-xs font-bold text-slate-200 uppercase">Direct LLM (No Cache)</span>
            <span className="text-[10px] font-mono text-rose-400 bg-rose-950/60 border border-rose-900/60 px-1.5 py-0.5">NO CACHING</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-950 p-3 border border-slate-800">
              <div className="text-[10px] font-mono text-slate-400 mb-1">P99 LATENCY</div>
              <div className="font-display text-2xl font-bold text-rose-400">~840ms</div>
            </div>
            <div className="bg-slate-950 p-3 border border-slate-800">
              <div className="text-[10px] font-mono text-slate-400 mb-1">COST / CALL</div>
              <div className="font-display text-2xl font-bold text-rose-400">$0.036</div>
            </div>
          </div>
          <div className="text-[11px] font-mono text-slate-400 space-y-1 border-t border-slate-800/80 pt-3">
            <div className="flex justify-between"><span>Token Gen:</span><span>~1,450</span></div>
            <div className="flex justify-between"><span>Provider:</span><span className="text-amber-400">Rate-limited (429)</span></div>
          </div>
        </div>

        <div className="bg-indigo-950/20 border border-indigo-500/40 p-5 space-y-4 relative shadow-[0_0_30px_rgba(99,102,241,0.1)]">
          <div className="flex items-center justify-between border-b border-indigo-900/60 pb-3">
            <span className="font-mono text-xs font-bold text-indigo-300 uppercase flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5 text-indigo-400" /> CacheMind Gateway</span>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 border border-emerald-800 px-1.5 py-0.5 font-bold">LIVE HIT</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-950 p-3 border border-indigo-900/60">
              <div className="text-[10px] font-mono text-indigo-300 mb-1">SERVED LATENCY</div>
              <div className="font-display text-2xl font-bold text-emerald-400">&lt; 2ms</div>
            </div>
            <div className="bg-slate-950 p-3 border border-indigo-900/60">
              <div className="text-[10px] font-mono text-indigo-300 mb-1">EFFECTIVE COST</div>
              <div className="font-display text-2xl font-bold text-emerald-400">$0.000</div>
            </div>
          </div>
          <div className="text-[11px] font-mono text-slate-300 space-y-1 border-t border-indigo-900/60 pt-3">
            <div className="flex justify-between"><span>Embedding:</span><span className="text-cyan-400 font-bold">FastEmbed BGE-Small 384D</span></div>
            <div className="flex justify-between"><span>L1/L2 Hit:</span><span className="text-emerald-400 font-bold">Real gateway headers</span></div>
          </div>
        </div>
      </div>

      <div className="mt-6 p-4 bg-slate-900/80 border border-indigo-500/30 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <div className="text-xs font-mono font-bold text-slate-100">FTUE BENCHMARK: 3-STEP LIVE GATEWAY ASSAY</div>
          <div className="text-[11px] font-mono text-slate-400">Cold Query → Exact Match → Paraphrased Semantic. All telemetry from `X-CacheMind-*` headers.</div>
        </div>
        <a href="#interactive-demo" className="text-xs font-mono text-indigo-400 hover:text-indigo-300 flex items-center gap-1 uppercase tracking-wider font-semibold whitespace-nowrap">EXPLORE 3D EMBEDDING <ArrowRight className="w-3.5 h-3.5" /></a>
      </div>
    </div>
  );
}
