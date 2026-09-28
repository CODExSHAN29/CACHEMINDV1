"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { PlaygroundResponse } from "@/lib/types";

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
        toast.success(`⚡ Exact Cache Hit! Latency: ${res.latency_ms}ms`);
      } else if (res.cache_status === "SEMANTIC_HIT") {
        toast.success(`🧠 Semantic Vector Hit! Similarity: ${(res.semantic_score || 0).toFixed(3)}`);
      } else {
        toast("Upstream Provider Call (Miss)", { icon: "🌐" });
      }
    } catch (err: any) {
      toast.error(`Inference error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Interactive Inference Playground</h2>
        <p className="text-sm text-gray-400 mt-1">
          Test Exact and Semantic caching live, measure latency acceleration, and verify PII masking.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Input Panel */}
        <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-dark-border">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <span>📝</span> Inference Request
              </h3>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="bg-dark-bg border border-dark-border rounded-lg px-2.5 py-1 text-xs text-white font-mono"
              >
                <option value="gpt-4o-mini">gpt-4o-mini</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">User Prompt</label>
              <textarea
                rows={5}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full bg-dark-bg border border-dark-border rounded-lg p-3 text-white text-xs font-mono focus:outline-none focus:border-blue-500"
                placeholder="Enter prompt..."
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Metadata Tags</label>
                <input
                  type="text"
                  placeholder="e.g. env:prod, v2"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Scope Namespace</label>
                <input
                  type="text"
                  placeholder="e.g. kb_support"
                  value={namespace}
                  onChange={(e) => setNamespace(e.target.value)}
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                />
              </div>
            </div>

            {/* Quick Test Presets */}
            <div className="pt-2">
              <span className="text-[11px] text-gray-500 block mb-1.5">Quick Test Scenarios:</span>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setPrompt("What is semantic caching in modern LLM gateways?")}
                  className="px-2.5 py-1 bg-dark-bg hover:bg-dark-hover border border-dark-border text-[11px] text-gray-300 rounded"
                >
                  Exact Seed
                </button>
                <button
                  onClick={() => setPrompt("Explain semantic caching for AI models")}
                  className="px-2.5 py-1 bg-dark-bg hover:bg-dark-hover border border-dark-border text-[11px] text-purple-300 rounded"
                >
                  Semantic Match (~94%)
                </button>
                <button
                  onClick={() => setPrompt("My user email is test.user@example.com and card is 4111 1111 1111 1111.")}
                  className="px-2.5 py-1 bg-dark-bg hover:bg-dark-hover border border-dark-border text-[11px] text-emerald-300 rounded"
                >
                  PII Masking Test
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={handleSend}
            disabled={loading}
            className="w-full mt-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/10"
          >
            <span>{loading ? "Routing through Gateway..." : "Execute Gateway Request"}</span>
          </button>
        </div>

        {/* Output Panel */}
        <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-dark-border">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <span>🤖</span> Gateway Response & Telemetry
              </h3>
              {response && (
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-0.5 rounded text-xs font-mono font-semibold ${
                      response.cache_status === "EXACT_HIT"
                        ? "bg-blue-950 text-blue-400 border border-blue-800"
                        : response.cache_status === "SEMANTIC_HIT"
                        ? "bg-purple-950 text-purple-400 border border-purple-800"
                        : "bg-gray-800 text-gray-300 border border-gray-700"
                    }`}
                  >
                    {response.cache_status}
                  </span>
                  <span className="text-xs text-emerald-400 font-mono">{response.latency_ms}ms</span>
                </div>
              )}
            </div>

            {response ? (
              <div className="mt-4 space-y-4">
                <div className="bg-dark-bg/80 border border-dark-border rounded-lg p-4 font-sans text-xs text-gray-200 leading-relaxed max-h-64 overflow-y-auto">
                  {response.choices?.[0]?.message?.content || "No content returned"}
                </div>

                {/* Telemetry Metrics Bar */}
                <div className="grid grid-cols-3 gap-3 text-xs font-mono pt-2">
                  <div className="bg-dark-bg p-2.5 rounded border border-dark-border">
                    <span className="text-gray-500 block text-[10px]">Roundtrip Time:</span>
                    <span className="text-white font-semibold">{response.latency_ms} ms</span>
                  </div>
                  <div className="bg-dark-bg p-2.5 rounded border border-dark-border">
                    <span className="text-gray-500 block text-[10px]">Tokens Saved:</span>
                    <span className="text-blue-400 font-semibold">{response.tokens_saved || 0}</span>
                  </div>
                  <div className="bg-dark-bg p-2.5 rounded border border-dark-border">
                    <span className="text-gray-500 block text-[10px]">Cost Saved:</span>
                    <span className="text-emerald-400 font-semibold">
                      ${(response.cost_saved_usd || 0).toFixed(4)}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-gray-500 text-xs text-center p-6 border border-dashed border-dark-border rounded-lg mt-4">
                <span className="text-2xl mb-2">⚡</span>
                <span>Send a prompt to test CacheMind Gateway acceleration, caching, and PII masking live.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
