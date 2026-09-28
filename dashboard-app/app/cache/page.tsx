"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { CacheInspection } from "@/lib/types";
import {
  Trash2,
  Flame,
  Search,
  Zap,
  Layers,
  Cpu,
  Database,
  ShieldAlert,
  CheckCircle2,
  RefreshCcw,
} from "lucide-react";

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
        `Purged ${res.exact_keys_removed} exact keys & ${res.semantic_vectors_removed} semantic vectors.`
      );
    } catch (err: any) {
      toast.error(`Purge execution error: ${err.message}`);
    } finally {
      setPurgeLoading(false);
    }
  };

  const handleInspect = async () => {
    if (!inspectKey.trim()) {
      toast.error("Input SHA-256 fingerprint hash for cache inspection");
      return;
    }
    setInspectLoading(true);
    try {
      const res = await api.inspectCacheKey(inspectKey.trim());
      setInspectionResult(res);
      if (res.found) {
        toast.success("Active cache record retrieved from memory pool.");
      } else {
        toast.error("Key not found or expired from TTL registry.");
      }
    } catch (err: any) {
      toast.error(`Inspection failure: ${err.message}`);
    } finally {
      setInspectLoading(false);
    }
  };

  const handleWarm = async () => {
    if (!warmPrompt.trim() || !warmCompletion.trim()) {
      toast.error("Both Prompt and Completion payload required for vector seeding");
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
      toast.success(`Successfully seeded ${res.seeded} record(s) into L1 exact and L2 vector index.`);
      setWarmPrompt("");
      setWarmCompletion("");
    } catch (err: any) {
      toast.error(`Pre-warming failure: ${err.message}`);
    } finally {
      setWarmLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-carbon-750/80">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-laser-amber font-semibold">
            SYS.ZONE // 03
          </span>
          <span className="text-slate-400 font-mono text-[10px]">
            :: [CACHE LIFECYCLE & VECTOR SEEDING ENGINE]
          </span>
        </div>
        <h2 className="text-xl md:text-2xl font-mono font-bold text-white tracking-tight mt-1">
          CACHE LIFECYCLE, SEEDING & PURGE CONTROLS
        </h2>
        <p className="text-xs font-mono text-slate-400 mt-0.5">
          Granular L1 exact key invalidation, FastEmbed ONNX pre-warming, and SHA-256 cache inspector.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scoped Invalidation */}
        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
            <div className="flex items-center gap-2">
              <Trash2 className="w-4 h-4 text-laser-crimson" />
              <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                SCOPED CACHE PURGE
              </h3>
            </div>
            <span className="text-[9px] font-mono text-laser-crimson bg-laser-crimson/10 border border-laser-crimson/30 px-1.5 py-0.5 rounded-sm font-semibold">
              ATOMIC PURGE
            </span>
          </div>
          <p className="text-xs font-mono text-slate-400">
            Evict matching exact cache keys and FastEmbed semantic vectors partitioned by model, namespace, or metadata tags.
          </p>

          <div className="space-y-3 font-mono text-xs">
            <div className="space-y-1">
              <label className="text-slate-400 uppercase tracking-wider text-[10px]">
                TARGET MODEL (OPTIONAL)
              </label>
              <input
                type="text"
                placeholder="e.g. gpt-4o-mini"
                value={purgeModel}
                onChange={(e) => setPurgeModel(e.target.value)}
                className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-crimson"
              />
            </div>

            <div className="space-y-1">
              <label className="text-slate-400 uppercase tracking-wider text-[10px]">
                FILTER TAGS (COMMA SEPARATED)
              </label>
              <input
                type="text"
                placeholder="e.g. env:prod, v2, internal"
                value={purgeTags}
                onChange={(e) => setPurgeTags(e.target.value)}
                className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-crimson"
              />
            </div>

            <button
              onClick={handlePurge}
              disabled={purgeLoading}
              className="w-full mt-2 py-2 bg-laser-crimson/90 hover:bg-laser-crimson text-white font-mono font-bold text-xs rounded-sm transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{purgeLoading ? "PURGING ENTRIES..." : "EXECUTE PURGE PIPELINE"}</span>
            </button>
          </div>
        </div>

        {/* Pre-warming Seeding */}
        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-laser-amber" />
              <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                PRE-WARM & SEED INDEX
              </h3>
            </div>
            <span className="text-[9px] font-mono text-laser-amber bg-laser-amber/10 border border-laser-amber/30 px-1.5 py-0.5 rounded-sm font-semibold">
              FASTEMBED ONNX
            </span>
          </div>
          <p className="text-xs font-mono text-slate-400">
            Synthesize vector embeddings and L1 exact hashes to pre-seed the cache ahead of production traffic bursts.
          </p>

          <div className="space-y-3 font-mono text-xs">
            <div className="space-y-1">
              <label className="text-slate-400 uppercase tracking-wider text-[10px]">
                PROMPT / QUERY PAYLOAD
              </label>
              <input
                type="text"
                placeholder="e.g. What is the SLA for CacheMind gateway?"
                value={warmPrompt}
                onChange={(e) => setWarmPrompt(e.target.value)}
                className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-amber"
              />
            </div>

            <div className="space-y-1">
              <label className="text-slate-400 uppercase tracking-wider text-[10px]">
                COMPLETION RESPONSE
              </label>
              <textarea
                rows={2}
                placeholder="e.g. CacheMind provides sub-millisecond cached responses with 99.99% availability..."
                value={warmCompletion}
                onChange={(e) => setWarmCompletion(e.target.value)}
                className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-amber"
              />
            </div>

            <button
              onClick={handleWarm}
              disabled={warmLoading}
              className="w-full mt-2 py-2 bg-laser-amber/90 hover:bg-laser-amber text-carbon-950 font-mono font-bold text-xs rounded-sm transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              <Flame className="w-3.5 h-3.5" />
              <span>{warmLoading ? "SEEDING VECTORS..." : "SEED L1 & L2 INDICES"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Cache Key Inspection Terminal */}
      <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-laser-cyan" />
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              CACHE KEY FINGERPRINT INSPECTION
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            [SHA-256 EXACT REGISTRY]
          </span>
        </div>

        <div className="flex flex-col sm:flex-row gap-2.5">
          <input
            type="text"
            placeholder="Input 64-character SHA-256 fingerprint hash..."
            value={inspectKey}
            onChange={(e) => setInspectKey(e.target.value)}
            className="flex-1 bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-cyan"
          />
          <button
            onClick={handleInspect}
            disabled={inspectLoading}
            className="px-4 py-2 bg-carbon-800 hover:bg-carbon-750 border border-carbon-700 text-xs font-mono font-semibold text-white rounded-sm transition-colors flex items-center justify-center gap-2"
          >
            <Search className="w-3.5 h-3.5 text-laser-cyan" />
            <span>{inspectLoading ? "INSPECTING..." : "QUERY RECORD"}</span>
          </button>
        </div>

        {inspectionResult && inspectionResult.found && (
          <div className="mt-3 bg-carbon-950 border border-carbon-750/80 rounded-sm p-4 space-y-2.5 text-xs font-mono">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pb-3 border-b border-carbon-750/60">
              <div>
                <span className="text-slate-400 block text-[10px]">MODEL:</span>
                <span className="text-white font-semibold">{inspectionResult.model}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">ACCESS COUNT:</span>
                <span className="text-laser-cyan font-semibold tabular-nums">
                  {inspectionResult.access_count}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">TTL REMAINING:</span>
                <span className="text-laser-emerald font-semibold tabular-nums">
                  {inspectionResult.ttl_remaining_seconds}s
                </span>
              </div>
            </div>

            <div>
              <span className="text-slate-400 block mb-1 text-[10px]">PAYLOAD PREVIEW:</span>
              <div className="bg-carbon-900 p-3 rounded-sm border border-carbon-750 font-mono text-slate-200 text-[11px] leading-relaxed">
                {inspectionResult.response_preview}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
