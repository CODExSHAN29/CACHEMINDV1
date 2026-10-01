"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { CacheInspection } from "@/lib/types";
import VectorClusterVisualizer from "@/components/three/VectorClusterVisualizer";
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
  const { activeWorkspace, activeProject } = useAuth();
  const [purgeModel, setPurgeModel] = useState("");
  const [purgeTags, setPurgeTags] = useState("");
  const [purgeLoading, setPurgeLoading] = useState(false);

  const [inspectKey, setInspectKey] = useState("");
  const [inspectionResult, setInspectionResult] = useState<CacheInspection | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);

  const [warmPrompt, setWarmPrompt] = useState("");
  const [warmCompletion, setWarmCompletion] = useState("");
  const [warmModel, setWarmModel] = useState("gpt-4o-mini");
  const [warmLoading, setWarmLoading] = useState(false);

  const handlePurge = async () => {
    if (!activeWorkspace?.id) {
      toast.error("No active workspace selected.");
      return;
    }
    setPurgeLoading(true);
    try {
      const tags = purgeTags ? purgeTags.split(",").map((t) => t.trim()) : undefined;
      const res = await api.purgeCache({
        tenant_id: activeWorkspace.id,
        project_id: activeProject?.id || undefined,
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
    if (!activeWorkspace?.id) {
      toast.error("No active workspace selected.");
      return;
    }
    setWarmLoading(true);
    try {
      const res = await api.warmCache({
        tenant_id: activeWorkspace.id,
        project_id: activeProject?.id || undefined,
        items: [
          {
            prompt: warmPrompt.trim(),
            completion: warmCompletion.trim(),
            model: warmModel,
          },
        ],
      });
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
      <div className="bg-surface border border-outline p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge-pill bg-amber-50 text-amber-800 border-amber-300 font-mono font-bold text-[10px]">
              SYS.ZONE // 03
            </span>
            <span className="text-on-surface-variant font-mono text-xs">
              :: [CACHE LIFECYCLE & VECTOR SEEDING ENGINE]
            </span>
          </div>
          <h1 className="text-2xl font-display font-bold text-on-surface uppercase tracking-tight mt-2">
            Cache Lifecycle, Seeding & Purge Controls
          </h1>
          <p className="text-xs font-sans text-on-surface-variant mt-1 max-w-3xl">
            Granular L1 exact key invalidation, FastEmbed ONNX pre-warming, and SHA-256 cache inspector.
          </p>
          <p className="text-[10px] font-mono text-slate-500 mt-2">
            WORKSPACE: {activeWorkspace?.name || activeWorkspace?.id || "AUTHENTICATING..."} {activeProject?.name ? `| PROJECT: ${activeProject.name}` : ""}
          </p>
        </div>
      </div>

      {/* 3D Semantic Vector Cache Manifold Visualizer */}
      <div className="space-y-2">
        <VectorClusterVisualizer />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scoped Invalidation */}
        <div className="bg-surface border border-outline p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Trash2 className="w-4 h-4 text-red-600" />
              <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
                SCOPED CACHE PURGE
              </h2>
            </div>
            <span className="text-[9px] font-mono text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 font-bold">
              ATOMIC PURGE
            </span>
          </div>
          <p className="text-xs font-mono text-on-surface-variant">
            Evict matching exact cache keys and FastEmbed semantic vectors partitioned by workspace, project, model, or metadata tags.
          </p>

          <div className="space-y-3 font-mono text-xs">
            <div className="space-y-1">
              <label className="label-caps">TARGET MODEL (OPTIONAL)</label>
              <input
                type="text"
                placeholder="e.g. gpt-4o-mini"
                value={purgeModel}
                onChange={(e) => setPurgeModel(e.target.value)}
                className="w-full bg-surface-dim border border-outline px-3 py-2 text-xs text-on-surface font-mono focus:outline-none focus:border-red-400"
              />
            </div>

            <div className="space-y-1">
              <label className="label-caps">FILTER TAGS (COMMA SEPARATED)</label>
              <input
                type="text"
                placeholder="e.g. env:prod, v2, internal"
                value={purgeTags}
                onChange={(e) => setPurgeTags(e.target.value)}
                className="w-full bg-surface-dim border border-outline px-3 py-2 text-xs text-on-surface font-mono focus:outline-none focus:border-red-400"
              />
            </div>

            <button
              onClick={handlePurge}
              disabled={purgeLoading}
              className="w-full mt-2 py-2.5 bg-red-600 hover:bg-red-700 text-white font-mono font-bold text-xs transition-colors flex items-center justify-center gap-2"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{purgeLoading ? "PURGING ENTRIES..." : "EXECUTE PURGE PIPELINE"}</span>
            </button>
          </div>
        </div>

        {/* Pre-warming Seeding */}
        <div className="bg-surface border border-outline p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-amber-600" />
              <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
                PRE-WARM & SEED INDEX
              </h2>
            </div>
            <span className="text-[9px] font-mono text-amber-800 bg-amber-50 border border-amber-200 px-1.5 py-0.5 font-bold">
              FASTEMBED ONNX
            </span>
          </div>
          <p className="text-xs font-mono text-on-surface-variant">
            Synthesize vector embeddings and L1 exact hashes to pre-seed the cache ahead of production traffic bursts.
          </p>

          <div className="space-y-3 font-mono text-xs">
            <div className="space-y-1">
              <label className="label-caps">PROMPT / QUERY PAYLOAD</label>
              <input
                type="text"
                placeholder="e.g. What is the SLA for CacheMind gateway?"
                value={warmPrompt}
                onChange={(e) => setWarmPrompt(e.target.value)}
                className="w-full bg-surface-dim border border-outline px-3 py-2 text-xs text-on-surface font-mono focus:outline-none focus:border-amber-400"
              />
            </div>

            <div className="space-y-1">
              <label className="label-caps">COMPLETION RESPONSE</label>
              <textarea
                rows={2}
                placeholder="e.g. CacheMind provides sub-millisecond cached responses with 99.99% availability..."
                value={warmCompletion}
                onChange={(e) => setWarmCompletion(e.target.value)}
                className="w-full bg-surface-dim border border-outline px-3 py-2 text-xs text-on-surface font-mono focus:outline-none focus:border-amber-400"
              />
            </div>

            <div className="space-y-1">
              <label className="label-caps">TARGET MODEL</label>
              <select
                value={warmModel}
                onChange={(e) => setWarmModel(e.target.value)}
                className="w-full bg-surface-dim border border-outline px-3 py-2 text-xs text-on-surface font-mono focus:outline-none focus:border-amber-400"
              >
                <option value="gpt-4o-mini">gpt-4o-mini</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
              </select>
            </div>

            <button
              onClick={handleWarm}
              disabled={warmLoading}
              className="w-full mt-2 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-mono font-bold text-xs transition-colors flex items-center justify-center gap-2"
            >
              <Flame className="w-3.5 h-3.5" />
              <span>{warmLoading ? "SEEDING VECTORS..." : "SEED L1 & L2 INDICES"}</span>
            </button>
          </div>
        </div>

        {/* Cache Key Inspection Terminal */}
        <div className="bg-surface border border-outline p-5 space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-primary" />
              <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
                CACHE KEY FINGERPRINT INSPECTION
              </h2>
            </div>
            <span className="text-[10px] font-mono text-on-surface-variant bg-surface-dim px-2 py-0.5 border border-outline-variant">
              [SHA-256 EXACT REGISTRY]
            </span>
          </div>

          <div className="flex flex-col sm:flex-row gap-2.5">
            <input
              type="text"
              placeholder="Input 64-character SHA-256 fingerprint hash..."
              value={inspectKey}
              onChange={(e) => setInspectKey(e.target.value)}
              className="flex-1 bg-surface-dim border border-outline px-3 py-2 text-xs text-on-surface font-mono focus:outline-none focus:border-primary"
            />
            <button
              onClick={handleInspect}
              disabled={inspectLoading}
              className="px-4 py-2 bg-surface-dim hover:bg-blue-50 border border-outline hover:border-primary text-xs font-mono font-semibold text-on-surface transition-colors flex items-center justify-center gap-2"
            >
              <Search className="w-3.5 h-3.5 text-primary" />
              <span>{inspectLoading ? "INSPECTING..." : "QUERY RECORD"}</span>
            </button>
          </div>

          {inspectionResult && inspectionResult.found && (
            <div className="mt-3 bg-surface-dim border border-outline p-4 space-y-2.5 text-xs font-mono">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pb-3 border-b border-outline-variant">
                <div>
                  <span className="text-on-surface-variant block text-[10px]">MODEL:</span>
                  <span className="text-on-surface font-semibold">{inspectionResult.model}</span>
                </div>
                <div>
                  <span className="text-on-surface-variant block text-[10px]">ACCESS COUNT:</span>
                  <span className="text-primary font-semibold tabular-nums">
                    {inspectionResult.access_count}
                  </span>
                </div>
                <div>
                  <span className="text-on-surface-variant block text-[10px]">TTL REMAINING:</span>
                  <span className="text-emerald-700 font-semibold tabular-nums">
                    {inspectionResult.ttl_remaining_seconds}s
                  </span>
                </div>
              </div>

              <div>
                <span className="text-on-surface-variant block mb-1 text-[10px]">PAYLOAD PREVIEW:</span>
                <div className="bg-surface border border-outline p-3 font-mono text-on-surface text-[11px] leading-relaxed">
                  {inspectionResult.response_preview}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
