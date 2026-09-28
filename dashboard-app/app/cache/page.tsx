"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { CacheInspection } from "@/lib/types";

export default function CacheEnginePage() {
  // Purge State
  const [purgeModel, setPurgeModel] = useState("");
  const [purgeTags, setPurgeTags] = useState("");
  const [purgeLoading, setPurgeLoading] = useState(false);

  // Inspect State
  const [inspectKey, setInspectKey] = useState("");
  const [inspectionResult, setInspectionResult] = useState<CacheInspection | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);

  // Pre-warm State
  const [warmPrompt, setWarmPrompt] = useState("");
  const [warmCompletion, setWarmCompletion] = useState("");
  const [warmModel, setWarmModel] = useState("gpt-4o-mini");
  const [warmLoading, setWarmLoading] = useState(false);

  const handlePurge = async () => {
    setPurgeLoading(true);
    try {
      const tags = purgeTags ? purgeTags.split(",").map((t) => t.trim()) : undefined;
      const res = await api.purgeCache({
        tenant_id: "tenant_default",
        model: purgeModel || undefined,
        tags,
      });
      toast.success(
        `Purged ${res.exact_keys_removed} exact keys & ${res.semantic_vectors_removed} semantic vectors!`
      );
    } catch (err: any) {
      toast.error(`Purge failed: ${err.message}`);
    } finally {
      setPurgeLoading(false);
    }
  };

  const handleInspect = async () => {
    if (!inspectKey.trim()) {
      toast.error("Please provide a cache key hash (SHA-256)");
      return;
    }
    setInspectLoading(true);
    try {
      const res = await api.inspectCacheKey(inspectKey.trim());
      setInspectionResult(res);
      if (res.found) {
        toast.success("Cache entry found!");
      } else {
        toast.error("Cache key not found or expired.");
      }
    } catch (err: any) {
      toast.error(`Inspection failed: ${err.message}`);
    } finally {
      setInspectLoading(false);
    }
  };

  const handleWarm = async () => {
    if (!warmPrompt.trim() || !warmCompletion.trim()) {
      toast.error("Please provide both prompt and completion");
      return;
    }
    setWarmLoading(true);
    try {
      const res = await api.warmCache([
        {
          prompt: warmPrompt.trim(),
          completion: warmCompletion.trim(),
          model: warmModel,
        },
      ]);
      toast.success(`Successfully pre-warmed ${res.seeded} cache entries into L1 & L2!`);
      setWarmPrompt("");
      setWarmCompletion("");
    } catch (err: any) {
      toast.error(`Pre-warming failed: ${err.message}`);
    } finally {
      setWarmLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Cache Lifecycle Management</h2>
        <p className="text-sm text-gray-400 mt-1">
          Inspect, pre-warm, and selectively invalidate L1 exact keys and L2 semantic vector indices.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Scoped Cache Purge */}
        <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-dark-border">
            <span className="text-xl">🧹</span>
            <h3 className="text-base font-semibold text-white">Granular Cache Invalidation</h3>
          </div>
          <p className="text-xs text-gray-400">
            Flush cache entries across Redis and pgvector matching target model, namespace, or metadata tags.
          </p>

          <div className="space-y-3 text-sm">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Target Model (Optional)</label>
              <input
                type="text"
                placeholder="e.g. gpt-4o-mini"
                value={purgeModel}
                onChange={(e) => setPurgeModel(e.target.value)}
                className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                Filter Tags (Optional, comma-separated)
              </label>
              <input
                type="text"
                placeholder="e.g. env:prod, v2"
                value={purgeTags}
                onChange={(e) => setPurgeTags(e.target.value)}
                className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <button
              onClick={handlePurge}
              disabled={purgeLoading}
              className="w-full mt-2 py-2.5 bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <span>{purgeLoading ? "Purging..." : "Execute Cache Invalidation"}</span>
            </button>
          </div>
        </div>

        {/* Cache Pre-Warming */}
        <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-dark-border">
            <span className="text-xl">🔥</span>
            <h3 className="text-base font-semibold text-white">Cache Pre-Warming & Seeding</h3>
          </div>
          <p className="text-xs text-gray-400">
            Pre-compute FastEmbed vector embeddings and exact hashes to warm cache before production traffic hits.
          </p>

          <div className="space-y-3 text-sm">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Prompt / Query</label>
              <input
                type="text"
                placeholder="e.g. What is CacheMind Gateway?"
                value={warmPrompt}
                onChange={(e) => setWarmPrompt(e.target.value)}
                className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Completion Response</label>
              <textarea
                rows={2}
                placeholder="e.g. CacheMind is a high-performance semantic caching gateway..."
                value={warmCompletion}
                onChange={(e) => setWarmCompletion(e.target.value)}
                className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-blue-500"
              />
            </div>

            <button
              onClick={handleWarm}
              disabled={warmLoading}
              className="w-full mt-2 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <span>{warmLoading ? "Seeding..." : "Seed into Cache Index"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Cache Key Inspection */}
      <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-dark-border">
          <span className="text-xl">🔍</span>
          <h3 className="text-base font-semibold text-white">Inspect Specific Cache Key</h3>
        </div>

        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Enter SHA-256 exact key hash or fingerprint..."
            value={inspectKey}
            onChange={(e) => setInspectKey(e.target.value)}
            className="flex-1 bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleInspect}
            disabled={inspectLoading}
            className="px-5 py-2 bg-dark-bg hover:bg-dark-hover border border-dark-border text-xs font-medium text-white rounded-lg transition-colors"
          >
            {inspectLoading ? "Inspecting..." : "Inspect"}
          </button>
        </div>

        {inspectionResult && inspectionResult.found && (
          <div className="mt-4 bg-dark-bg/80 border border-dark-border rounded-lg p-4 space-y-2 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-gray-500">Model:</span>
              <span className="text-white">{inspectionResult.model}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Access Count:</span>
              <span className="text-blue-400">{inspectionResult.access_count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">TTL Remaining:</span>
              <span className="text-emerald-400">{inspectionResult.ttl_remaining_seconds}s</span>
            </div>
            <div className="pt-2 border-t border-dark-border">
              <span className="text-gray-500 block mb-1">Response Preview:</span>
              <p className="text-gray-300 font-sans text-xs bg-dark-card p-2 rounded border border-dark-border">
                {inspectionResult.response_preview}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
