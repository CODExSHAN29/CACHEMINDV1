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
  Check,
  Layers,
  ArrowRight,
  Shield,
  RefreshCw,
  SlidersHorizontal,
  Info,
  Code,
} from "lucide-react";

export default function PlaygroundPage() {
  const [prompt, setPrompt] = useState("What is semantic caching in modern LLM gateways?");
  const [model, setModel] = useState("gpt-4o-mini");
  const [tags, setTags] = useState("");
  const [namespace, setNamespace] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<PlaygroundResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSend = async () => {
    if (!prompt.trim()) {
      toast.error("Please enter a prompt buffer");
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
        toast.success(`L2 Semantic Hit [FastEmbed]: ${(res.semantic_score || 0).toFixed(3)} Cosine`);
      } else {
        toast.success(`Upstream Dispatch: ${res.latency_ms}ms`);
      }
    } catch (err: any) {
      toast.error(`Inference error: ${err.message || "Gateway unavailable"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Copied to clipboard");
  };

  return (
    <div className="space-y-6">
      {/* Precision Dossier Header */}
      <div className="bg-surface border border-outline p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge-pill bg-primary text-white border-primary">
              SYS.ZONE // 06
            </span>
            <span className="text-on-surface-variant font-mono text-xs">
              :: [INTERACTIVE INFERENCE & TELEMETRY CONSOLE]
            </span>
          </div>
          <h1 className="text-2xl font-display font-bold text-on-surface uppercase tracking-tight mt-2">
            Inference Playground & Real-Time Cache Benchmark
          </h1>
          <p className="text-xs font-sans text-on-surface-variant mt-1 max-w-3xl">
            Execute prompt inference queries against the CacheMind gateway. Observe live deterministic L1 (SHA-256) exact recovery,
            quantized L2 (FastEmbed ONNX) semantic similarity arbitration, sub-millisecond TTFT, and automated PII scrub verification.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="badge-pill bg-emerald-50 text-emerald-700 border-emerald-300 font-bold">
            LATENCY TARGET: &lt;1.0ms
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Control Panel */}
        <div className="bg-surface border border-outline p-5 space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-primary" />
                <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
                  INFERENCE PAYLOAD BUFFER
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-on-surface-variant uppercase">MODEL:</span>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="bg-surface-dim border border-outline px-2.5 py-1 text-xs text-on-surface font-mono focus:outline-none focus:border-primary"
                >
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="gpt-4o">gpt-4o</option>
                  <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="label-caps block">PROMPT / QUERY TEXT BUFFER</label>
              <textarea
                rows={5}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full bg-surface-dim border border-outline p-3 text-on-surface text-xs font-mono focus:outline-none focus:border-primary leading-relaxed"
                placeholder="Enter prompt buffer for gateway inference dispatch..."
              />
            </div>

            <div className="grid grid-cols-2 gap-3 font-mono text-xs">
              <div className="space-y-1">
                <label className="label-caps block">METADATA TAGS [CSV]</label>
                <input
                  type="text"
                  placeholder="e.g. env:prod, v2"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full bg-surface-dim border border-outline px-3 py-1.5 text-xs text-on-surface font-mono focus:outline-none focus:border-primary"
                />
              </div>
              <div className="space-y-1">
                <label className="label-caps block">NAMESPACE SCOPE</label>
                <input
                  type="text"
                  placeholder="e.g. kb_support"
                  value={namespace}
                  onChange={(e) => setNamespace(e.target.value)}
                  className="w-full bg-surface-dim border border-outline px-3 py-1.5 text-xs text-on-surface font-mono focus:outline-none focus:border-primary"
                />
              </div>
            </div>

            {/* Quick Test Presets */}
            <div className="pt-3 border-t border-outline-variant space-y-2">
              <span className="label-caps block">BENCHMARK SCENARIO PRESETS:</span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <button
                  onClick={() => setPrompt("What is semantic caching in modern LLM gateways?")}
                  className="p-2 bg-surface-dim hover:bg-blue-50 border border-outline hover:border-primary text-left text-on-surface transition-all flex flex-col"
                >
                  <span className="font-mono font-bold text-[11px] text-primary">[01] Exact L1 Seed</span>
                  <span className="text-[9px] font-mono text-on-surface-variant">0.85ms // Exact Hash</span>
                </button>
                <button
                  onClick={() => setPrompt("Explain semantic caching for AI models")}
                  className="p-2 bg-surface-dim hover:bg-blue-50 border border-outline hover:border-primary text-left text-on-surface transition-all flex flex-col"
                >
                  <span className="font-mono font-bold text-[11px] text-secondary">[02] Semantic L2 Match</span>
                  <span className="text-[9px] font-mono text-on-surface-variant">4.20ms // ~0.94 Cosine</span>
                </button>
                <button
                  onClick={() => setPrompt("Validate customer auth for SSN 049-21-9981 with Visa 4111-2222-3333-4444.")}
                  className="p-2 bg-surface-dim hover:bg-amber-50 border border-outline hover:border-amber-400 text-left text-on-surface transition-all flex flex-col"
                >
                  <span className="font-mono font-bold text-[11px] text-amber-800">[03] Luhn PII Mask</span>
                  <span className="text-[9px] font-mono text-on-surface-variant">&lt;0.25ms // Redacted</span>
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={handleSend}
            disabled={loading}
            className="btn-solid w-full mt-4 bg-primary text-white border-primary hover:bg-blue-800 font-mono font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>{loading ? "ROUTING GATEWAY PIPELINE..." : "EXECUTE INFERENCE DISPATCH"}</span>
          </button>
        </div>

        {/* Output Telemetry & Response Panel */}
        <div className="bg-surface border border-outline p-5 space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-primary" />
                <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
                  GATEWAY TELEMETRY RESPONSE
                </h2>
              </div>
              {response && (
                <div className="flex items-center gap-2">
                  <span
                    className={`badge-pill font-mono font-bold ${
                      response.cache_status === "EXACT_HIT"
                        ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                        : response.cache_status === "SEMANTIC_HIT"
                        ? "bg-blue-50 text-primary border-blue-300"
                        : "bg-surface-dim text-on-surface-variant border-outline-variant"
                    }`}
                  >
                    {response.cache_status}
                  </span>
                  <span className="text-xs font-mono text-primary font-bold tabular-nums">
                    {response.latency_ms} ms
                  </span>
                </div>
              )}
            </div>

            {response ? (
              <div className="space-y-4">
                {/* Response Content Box */}
                <div className="relative">
                  <div className="flex items-center justify-between bg-surface-dim px-3 py-1.5 border border-outline border-b-0 text-[10px] font-mono text-on-surface-variant font-bold">
                    <span>INFERENCE STREAM OUTPUT</span>
                    <button
                      onClick={() => handleCopy(response.choices?.[0]?.message?.content || "")}
                      className="flex items-center gap-1 text-primary hover:underline"
                    >
                      {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                      <span>{copied ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="bg-surface border border-outline p-4 font-mono text-xs text-on-surface leading-relaxed max-h-64 overflow-y-auto whitespace-pre-wrap">
                    {response.choices?.[0]?.message?.content || "No content returned"}
                  </div>
                </div>

                {/* Telemetry Metrics HUD */}
                <div className="grid grid-cols-3 gap-2 text-xs font-mono pt-1">
                  <div className="bg-surface-dim p-2.5 border border-outline">
                    <span className="label-caps text-[9px] block">ROUNDTRIP LATENCY:</span>
                    <span className="text-primary font-bold tabular-nums mt-0.5 block">{response.latency_ms} ms</span>
                  </div>
                  <div className="bg-surface-dim p-2.5 border border-outline">
                    <span className="label-caps text-[9px] block">TOKENS AVOIDED:</span>
                    <span className="text-on-surface font-bold tabular-nums mt-0.5 block">{response.tokens_saved || 0}</span>
                  </div>
                  <div className="bg-surface-dim p-2.5 border border-outline">
                    <span className="label-caps text-[9px] block">FINANCIAL ROI:</span>
                    <span className="text-emerald-700 font-bold tabular-nums mt-0.5 block">
                      ${(response.cost_saved_usd || 0).toFixed(4)}
                    </span>
                  </div>
                </div>

                {/* Scored Metadata Trace */}
                {response.semantic_score && (
                  <div className="bg-secondary-container border border-blue-200 p-3 font-mono text-xs flex items-center justify-between text-primary">
                    <span className="font-bold">L2 FastEmbed Cosine Similarity:</span>
                    <span className="font-bold tabular-nums">{(response.semantic_score).toFixed(4)} (Threshold: &gt;0.900)</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-on-surface-variant text-xs font-mono text-center p-6 border border-dashed border-outline bg-surface-dim">
                <Zap className="w-8 h-8 mb-2 text-primary animate-pulse" />
                <span className="text-on-surface font-bold uppercase tracking-wider">AWAITING INFERENCE EXECUTION</span>
                <span className="text-[11px] text-on-surface-variant mt-1 max-w-xs leading-relaxed">
                  Dispatch a query from the left buffer to benchmark sub-millisecond cache latency, FastEmbed semantic matching, and PII masking.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
