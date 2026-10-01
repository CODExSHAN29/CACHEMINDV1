"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { APIKeyInfo } from "@/lib/types";
import { KeyRound, Copy, Check, Trash2, Plus, ShieldCheck, AlertTriangle, FolderGit2 } from "lucide-react";

export default function KeysPage() {
  const { activeWorkspace, projects, activeProject, switchProject } = useAuth();
  const [name, setName] = useState("");
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");
  const [keys, setKeys] = useState<APIKeyInfo[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(false);

  const fetchKeys = useCallback(async () => {
    if (!activeProject?.id && !projects.length) {
      setKeys([]);
      return;
    }
    const targetProjId = activeProject?.id || projects[0]?.id;
    if (!targetProjId) return;

    setLoadingKeys(true);
    try {
      const list = await api.listAPIKeys(targetProjId);
      setKeys(list);
    } catch (e: any) {
      console.error("Failed to list API keys:", e);
    } finally {
      setLoadingKeys(false);
    }
  }, [activeProject, projects]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const targetProjId = activeProject?.id || projects[0]?.id;
    if (!targetProjId) {
      setError("No active project found to associate with this key.");
      return;
    }
    if (!name.trim()) {
      setError("Key name required.");
      return;
    }

    setIsCreating(true);
    setError("");
    setRawKey(null);

    try {
      const result = await api.createAPIKey(targetProjId, name.trim(), "admin");
      if (result && result.raw_key) {
        setRawKey(result.raw_key);
        setName("");
        fetchKeys();
      } else {
        setError("Key creation failed. Retry.");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to create API key.");
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (keyId: string) => {
    try {
      await api.revokeAPIKey(keyId);
      fetchKeys();
    } catch (e: any) {
      setError(e?.message || "Failed to revoke key.");
    }
  };

  return (
    <div className="max-w-3xl space-y-8">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-950/60 border border-indigo-600/50 flex items-center justify-center text-indigo-400">
            <KeyRound className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl tracking-tight">API KEY MANAGEMENT</h1>
            <p className="text-xs font-mono text-slate-400">
              TENANT: {activeWorkspace?.name || activeWorkspace?.id || "N/A"}
            </p>
          </div>
        </div>

        {projects.length > 1 && (
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs font-mono">
            <FolderGit2 className="w-3.5 h-3.5 text-indigo-400" />
            <select
              value={activeProject?.id || ""}
              onChange={(e) => switchProject(e.target.value)}
              aria-label="Select active project"
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id} className="bg-slate-950 text-slate-200">
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="bg-slate-950/60 border border-slate-800 p-5 sm:p-6 space-y-4 shadow-[0_0_30px_rgba(99,102,241,0.06)]">
        <form onSubmit={handleCreate} className="space-y-3">
          <label htmlFor="key-name" className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-wider">
            New Project Key Name (Project: {activeProject?.name || projects[0]?.name || "Default"})
          </label>
          <div className="flex gap-2">
            <input
              id="key-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="production-key-01"
              className="flex-1 px-3 py-2.5 bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-600"
            />
            <button
              type="submit"
              disabled={isCreating || !name.trim() || (!activeProject?.id && !projects.length)}
              className="btn-primary text-xs font-mono px-4 py-2.5 flex items-center gap-2 whitespace-nowrap shadow-xl shadow-indigo-900/30"
            >
              {isCreating ? (
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              <span>CREATE KEY</span>
            </button>
          </div>
          {error && <div className="p-2.5 bg-rose-950/60 border border-rose-900 text-rose-300 text-xs font-mono">{error}</div>}
        </form>

        {/* One-time raw key reveal modal */}
        {rawKey && (
          <div className="relative p-5 bg-indigo-950/30 border border-indigo-500/40 shadow-[0_0_40px_rgba(99,102,241,0.15)]">
            <div className="absolute top-0 right-0 p-2">
              <button onClick={() => setRawKey(null)} className="text-xs font-mono text-indigo-300 hover:text-white">
                DISMISS
              </button>
            </div>
            <div className="flex items-center gap-2 mb-2 text-indigo-300 font-bold text-xs font-mono">
              <ShieldCheck className="w-4 h-4" /> ONE-TIME SECRET — COPY NOW
            </div>
            <div className="flex items-center gap-2 bg-[#07090e] border border-indigo-800/50 p-2 font-mono text-xs text-indigo-200 break-all">
              <span>{rawKey}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(rawKey);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="shrink-0 p-1.5 bg-indigo-900 border border-indigo-500/50 text-indigo-200 hover:bg-indigo-800 transition-colors"
                title="Copy to clipboard"
              >
                {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-[10px] font-mono text-amber-400">
              <AlertTriangle className="w-3 h-3" /> This raw key is shown exactly once and is not recoverable.
            </div>
          </div>
        )}

        <div className="border-t border-slate-800 pt-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-widest">
              Active Keys — {keys.length}
            </h3>
            {loadingKeys && (
              <span className="text-[10px] font-mono text-slate-500 animate-pulse">Syncing...</span>
            )}
          </div>
          {keys.length === 0 ? (
            <div className="text-xs font-mono text-slate-500 py-2">
              {loadingKeys ? "Loading keys..." : "No API keys provisioned for this project."}
            </div>
          ) : (
            <div className="space-y-2">
              {keys.map((k) => (
                <div
                  key={k.id}
                  className="flex items-center justify-between px-3 py-2.5 bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-colors"
                >
                  <div>
                    <div className="text-xs font-mono font-bold text-slate-200 flex items-center gap-2">
                      <span>{k.name}</span>
                      <span className="text-[10px] px-1.5 py-0.2 bg-slate-800 text-indigo-300 font-normal">
                        {k.key_prefix}…
                      </span>
                    </div>
                    <div className="text-[10px] font-mono text-slate-500">
                      ID: {k.id} • Role: {k.role} • Created {new Date(k.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(k.id)}
                    className="p-1.5 text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 border border-transparent hover:border-rose-900/60 transition-all"
                    title="Revoke Key"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-slate-950/60 border border-slate-800 p-4 text-[10px] font-mono text-slate-400 leading-relaxed">
        <strong className="text-slate-300">SECURITY POLICY — RAW KEY LIFECYCLE:</strong> Keys are returned once by the gateway and never persisted to browser storage (localStorage/sessionStorage) or disk. Copy to clipboard immediately. If lost, revoke and regenerate.
      </div>
    </div>
  );
}
