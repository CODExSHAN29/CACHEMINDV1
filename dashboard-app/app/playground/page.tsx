"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { PlaygroundResponse } from "@/lib/types";
import {
  Terminal,
  Zap,
  Cpu,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Coins,
  Copy,
  Layers,
  ArrowRight,
} from "lucide-react";

export default function PlaygroundPage() {
  const [prompt, setPrompt] = useState("What is semantic caching in modern LLM gateways?");
  const [model, setModel] = useState("gpt-4o-mini");
  const [tags, setTags] = useState("");
  const [namespace, setNamespace] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<PlaygroundResponse | null>(null);

  const handleSend = async () => {
    if (!prompt.trim()) {
      toast.error("Please enter a prompt");
      return;
    }
    setLoading(true);
    try {
      const tagList = tags ? tags.split(",").map((t) => t.trim()) : undefined;
      const res = await api.sendPlaygroundInference(
        prompt.trim(),
        model,
        tagList,
        namespace.trim() || undefined
      );
      setResponse(res);
      if (res.cache_status === "EXACT_HIT") {
        toast.success(`L1 Exact Hit [SHA-256]: ${res.latency_ms}ms`);
      } else if (res.cache_status === "SEMANTIC_HIT") {
        toast.success(`L2 Semantic Hit [FastEmbed]: Similarity ${(res.semantic_score || 0).toFixed(3)}`);
      } else {
        toast.success(`Upstream Dispatched: ${res.latency_ms}ms`);
      }
    } catch (err: any) {
      toast.error(`Inference error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-carbon-750/80">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-laser-emerald font-semibold">
            SYS.ZONE // 06
          </span>
          <span className="text-slate-400 font-mono text-[10px]">
            :: [INTERACTIVE INFERENCE & TELEMETRY CONSOLE]
          </span>
        </div>
        <h2 className="text-xl md:text-2xl font-mono font-bold text-white tracking-tight mt-1">
          INFERENCE PLAYGROUND & REAL-TIME CACHE BENCHMARK
        </h2>
        <p className="text-xs font-mono text-slate-400 mt-0.5">
          Execute prompt inference queries, audit L1/L2 cache hit status, measure sub-millisecond TTFT, and test PII sanitization.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Panel */}
        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-laser-emerald" />
                <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                  INFERENCE PAYLOAD
                </h3>
              </div>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="bg-carbon-950 border border-carbon-750 rounded-sm px-2.5 py-1 text-xs text-slate-200 font-mono focus:outline-none focus:border-laser-emerald"
              >
                <option value="gpt-4o-mini">gpt-4o-mini</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-slate-400 uppercase tracking-wider text-[10px] font-mono">
                PROMPT / QUERY BUFFER
              </label>
              <textarea
                rows={5}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full bg-carbon-950 border border-carbon-750 rounded-sm p-3 text-slate-100 text-xs font-mono focus:outline-none focus:border-laser-emerald"
                placeholder="Enter prompt buffer..."
              />
            </div>

            <div className="grid grid-cols-2 gap-3 font-mono text-xs">
              <div className="space-y-1">
                <label className="text-slate-400 uppercase tracking-wider text-[10px]">
                  METADATA TAGS
                </label>
                <input
                  type="text"
                  placeholder="e.g. env:prod, v2"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-laser-emerald"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-400 uppercase tracking-wider text-[10px]">
                  NAMESPACE SCOPE
                </label>
                <input
                  type="text"
                  placeholder="e.g. kb_support"
                  value={namespace}
                  onChange={(e) => setNamespace(e.target.value)}
                  className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-laser-emerald"
                />
              </div>
            </div>

            {/* Quick Test Presets */}
            <div className="pt-2 border-t border-carbon-750/50">
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-2">
                SCENARIO BENCHMARK PRESETS:
              </span>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setPrompt("What is semantic caching in modern LLM gateways?")}
                  className="px-2.5 py-1 bg-carbon-950 hover:bg-carbon-800 border border-carbon-750 text-[10px] font-mono text-slate-300 rounded-sm transition-colors"
                >
                  [01] Exact L1 Seed
                </button>
                <button
                  onClick={() => setPrompt("Explain semantic caching for AI models")}
                  className="px-2.5 py-1 bg-carbon-950 hover:bg-carbon-800 border border-carbon-750 text-[10px] font-mono text-laser-cyan rounded-sm transition-colors"
                >
                  [02] Semantic L2 Match (~94%)
                </button>
                <button
                  onClick={() => setPrompt("My email is security.lead@acme.corp and credit card is 4111 1111 1111 1111.")}
                  className="px-2.5 py-1 bg-carbon-950 hover:bg-carbon-800 border border-carbon-750 text-[10px] font-mono text-laser-amber rounded-sm transition-colors"
                >
                  [03] Luhn PII Masking
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={handleSend}
            disabled={loading}
            className="w-full mt-4 py-2.5 bg-laser-emerald hover:bg-emerald-400 text-carbon-950 font-mono font-bold text-xs uppercase tracking-wider rounded-sm transition-colors flex items-center justify-center gap-2 shadow-sm"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>{loading ? "ROUTING GATEWAY PIPELINE..." : "EXECUTE INFERENCE DISPATCH"}</span>
          </button>
        </div>

        {/* Output Panel */}
        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-laser-cyan" />
                <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                  GATEWAY TELEMETRY RESPONSE
                </h3>
              </div>
              {response && (
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold uppercase ${
                      response.cache_status === "EXACT_HIT"
                        ? "bg-laser-emerald/10 text-laser-emerald border border-laser-emerald/30"
                        : response.cache_status === "SEMANTIC_HIT"
                        ? "bg-laser-cyan/10 text-laser-cyan border border-laser-cyan/30"
                        : "bg-carbon-800 text-slate-300 border border-carbon-700"
                    }`}
                  >
                    {response.cache_status}
                  </span>
                  <span className="text-[11px] font-mono text-laser-emerald font-bold tabular-nums">
                    {response.latency_ms}ms
                  </span>
                </div>
              )}
            </div>

            {response ? (
              <div className="mt-4 space-y-4">
                <div className="bg-carbon-950 border border-carbon-750 rounded-sm p-4 font-mono text-xs text-slate-200 leading-relaxed max-h-64 overflow-y-auto">
                  {response.choices?.[0]?.message?.content || "No content returned"}
                </div>

                {/* Telemetry Metrics Bar */}
                <div className="grid grid-cols-3 gap-3 text-xs font-mono pt-2">
                  <div className="bg-carbon-950 p-2.5 rounded-sm border border-carbon-750">
                    <span className="text-slate-400 block text-[10px]">ROUNDTRIP LATENCY:</span>
                    <span className="text-white font-bold tabular-nums">{response.latency_ms} ms</span>
                  </div>
                  <div className="bg-carbon-950 p-2.5 rounded-sm border border-carbon-750">
                    <span className="text-slate-400 block text-[10px]">TOKENS AVOIDED:</span>
                    <span className="text-laser-cyan font-bold tabular-nums">{response.tokens_saved || 0}</span>
                  </div>
                  <div className="bg-carbon-950 p-2.5 rounded-sm border border-carbon-750">
                    <span className="text-slate-400 block text-[10px]">FINANCIAL ROI:</span>
                    <span className="text-laser-emerald font-bold tabular-nums">
                      ${(response.cost_saved_usd || 0).toFixed(4)}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-xs font-mono text-center p-6 border border-dashed border-carbon-750/80 rounded-sm mt-4">
                <Zap className="w-8 h-8 mb-2 text-carbon-600 animate-pulse" />
                <span className="text-slate-400 font-semibold uppercase tracking-wider">AWAITING INFERENCE EXECUTION</span>
                <span className="text-[11px] text-slate-500 mt-1 max-w-xs">
                  Dispatch a query to benchmark sub-millisecond cache latency, FastEmbed semantic matching, and PII masking.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
