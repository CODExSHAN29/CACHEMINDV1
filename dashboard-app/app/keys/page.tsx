"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { APIKeyInfo, ProjectInfo, TenantInfo } from "@/lib/types";
import {
  KeyRound,
  Building,
  FolderGit2,
  Plus,
  Trash2,
  Copy,
  ShieldCheck,
  Check,
  AlertTriangle,
} from "lucide-react";

export default function KeysAndProjectsPage() {
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [keys, setKeys] = useState<APIKeyInfo[]>([]);
  const [selectedTenant, setSelectedTenant] = useState("tenant_default");
  const [selectedProject, setSelectedProject] = useState("proj_default");

  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyRole, setNewKeyRole] = useState("inference");
  const [createdRawKey, setCreatedRawKey] = useState<string | null>(null);

  const [newTenantName, setNewTenantName] = useState("");
  const [newProjectName, setNewProjectName] = useState("");

  const refreshData = async () => {
    try {
      const tList = await api.listTenants();
      setTenants(tList);
      const pList = await api.listProjects(selectedTenant);
      setProjects(pList);
      const kList = await api.listAPIKeys(selectedProject);
      setKeys(kList);
    } catch (e: any) {
      console.error(e);
    }
  };

  useEffect(() => {
    refreshData();
  }, [selectedTenant, selectedProject]);

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      toast.error("Please specify an API key identifier");
      return;
    }
    try {
      const res = await api.createAPIKey(selectedProject, newKeyName.trim(), newKeyRole);
      toast.success("Cryptographic API Key generated successfully.");
      if (res.raw_key) {
        setCreatedRawKey(res.raw_key);
      }
      setNewKeyName("");
      refreshData();
    } catch (e: any) {
      toast.error(`Key creation failed: ${e.message}`);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm("Confirm key revocation? Inactive tokens immediately return 401 Unauthorized.")) {
      return;
    }
    try {
      await api.revokeAPIKey(keyId);
      toast.success("API key revoked from registry.");
      refreshData();
    } catch (e: any) {
      toast.error(`Revocation failed: ${e.message}`);
    }
  };

  const handleCreateTenant = async () => {
    if (!newTenantName.trim()) return;
    try {
      await api.createTenant(newTenantName.trim());
      toast.success("Tenant partition provisioned.");
      setNewTenantName("");
      refreshData();
    } catch (e: any) {
      toast.error(`Tenant creation failed: ${e.message}`);
    }
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      await api.createProject(selectedTenant, newProjectName.trim());
      toast.success("Project workspace provisioned.");
      setNewProjectName("");
      refreshData();
    } catch (e: any) {
      toast.error(`Project creation failed: ${e.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-carbon-750/80">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-laser-emerald font-semibold">
            SYS.ZONE // 04
          </span>
          <span className="text-slate-400 font-mono text-[10px]">
            :: [IAM & MULTI-TENANT ISOLATION PLANE]
          </span>
        </div>
        <h2 className="text-xl md:text-2xl font-mono font-bold text-white tracking-tight mt-1">
          API KEYS & MULTI-TENANT ACCESS CONTROL
        </h2>
        <p className="text-xs font-mono text-slate-400 mt-0.5">
          Provision tenant partitions, isolate project namespaces, and issue SHA-256 hashed API keys.
        </p>
      </div>

      {/* Tenant / Project Provisioning Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Tenant Box */}
        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-carbon-750/70">
            <div className="flex items-center gap-2">
              <Building className="w-4 h-4 text-laser-emerald" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                TENANT PARTITIONS
              </h3>
            </div>
            <span className="text-[10px] text-slate-400">
              COUNT: [{tenants.length}]
            </span>
          </div>

          <select
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-emerald"
          >
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} [{t.id}]
              </option>
            ))}
          </select>

          <div className="flex gap-2 pt-1">
            <input
              type="text"
              placeholder="Tenant Label (e.g. Org Alpha)..."
              value={newTenantName}
              onChange={(e) => setNewTenantName(e.target.value)}
              className="flex-1 bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-laser-emerald"
            />
            <button
              onClick={handleCreateTenant}
              className="px-3 py-1.5 bg-carbon-800 hover:bg-carbon-750 border border-carbon-700 text-laser-emerald text-xs rounded-sm font-bold flex items-center gap-1.5 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>PROVISION</span>
            </button>
          </div>
        </div>

        {/* Project Box */}
        <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-carbon-750/70">
            <div className="flex items-center gap-2">
              <FolderGit2 className="w-4 h-4 text-laser-cyan" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                PROJECT WORKSPACES
              </h3>
            </div>
            <span className="text-[10px] text-slate-400">
              COUNT: [{projects.length}]
            </span>
          </div>

          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-cyan"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} [{p.id}]
              </option>
            ))}
          </select>

          <div className="flex gap-2 pt-1">
            <input
              type="text"
              placeholder="Project Label (e.g. LLM Inference Service)..."
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="flex-1 bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-laser-cyan"
            />
            <button
              onClick={handleCreateProject}
              className="px-3 py-1.5 bg-carbon-800 hover:bg-carbon-750 border border-carbon-700 text-laser-cyan text-xs rounded-sm font-bold flex items-center gap-1.5 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>PROVISION</span>
            </button>
          </div>
        </div>
      </div>

      {/* Key Generation Form */}
      <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
          <div className="flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-laser-emerald" />
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              ISSUE LIVE SCOPED API TOKEN
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            TARGET: [{selectedProject}]
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
          <div className="space-y-1">
            <label className="text-slate-400 uppercase tracking-wider text-[10px]">
              KEY IDENTIFIER / NAME
            </label>
            <input
              type="text"
              placeholder="e.g. PROD-API-GATEWAY-INFERENCE"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 text-xs font-mono focus:outline-none focus:border-laser-emerald"
            />
          </div>

          <div className="space-y-1">
            <label className="text-slate-400 uppercase tracking-wider text-[10px]">
              ROLE / PERMISSION SCOPE
            </label>
            <select
              value={newKeyRole}
              onChange={(e) => setNewKeyRole(e.target.value)}
              className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 text-xs font-mono focus:outline-none focus:border-laser-emerald"
            >
              <option value="inference">inference (Chat, Streaming, Normalization)</option>
              <option value="read_only">read_only (Metrics, Telemetry Audit)</option>
              <option value="admin">admin (Full Cluster Control Plane)</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleCreateKey}
              className="w-full py-2 bg-laser-emerald text-carbon-950 font-mono font-bold text-xs rounded-sm hover:bg-emerald-400 transition-colors flex items-center justify-center gap-1.5 shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>GENERATE SECRET KEY</span>
            </button>
          </div>
        </div>

        {createdRawKey && (
          <div className="mt-3 p-4 bg-carbon-950 border border-laser-emerald/40 rounded-sm space-y-2">
            <div className="flex items-center gap-2 text-xs font-mono text-laser-emerald font-semibold">
              <AlertTriangle className="w-4 h-4 text-laser-amber" />
              <span>SECRET KEY GENERATED — STORE IMMEDIATELY:</span>
            </div>
            <div className="flex items-center justify-between font-mono text-xs text-white bg-carbon-900 p-2.5 rounded-sm border border-carbon-750">
              <span className="text-laser-emerald select-all">{createdRawKey}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(createdRawKey);
                  toast.success("Secret API key copied to clipboard.");
                }}
                className="flex items-center gap-1 text-[11px] font-mono text-slate-300 hover:text-white px-2 py-1 bg-carbon-800 rounded-sm border border-carbon-700 transition-colors"
              >
                <Copy className="w-3 h-3" />
                <span>COPY</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Active API Keys Table */}
      <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-3">
        <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-laser-emerald" />
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              ACTIVE ACCESS TOKENS IN REGISTRY
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            TOTAL: [{keys.length}]
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-300">
            <thead className="bg-carbon-950 text-[10px] text-slate-400 uppercase tracking-wider border-b border-carbon-750">
              <tr>
                <th className="py-2.5 px-4">IDENTIFIER</th>
                <th className="py-2.5 px-4">PREFIX</th>
                <th className="py-2.5 px-4">SCOPE</th>
                <th className="py-2.5 px-4">CREATED</th>
                <th className="py-2.5 px-4">STATUS</th>
                <th className="py-2.5 px-4 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-carbon-750/60">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-carbon-850/60 transition-colors">
                  <td className="py-3 px-4 font-bold text-white">{k.name}</td>
                  <td className="py-3 px-4 text-slate-400">{k.key_prefix}...</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded-sm bg-laser-cyan/10 text-laser-cyan border border-laser-cyan/30 text-[10px] font-semibold uppercase">
                      {k.role}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-400 tabular-nums">
                    {new Date(k.created_at).toISOString().substring(0, 10)}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-laser-emerald text-[11px] font-semibold flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-laser-emerald status-led"></span>
                      ACTIVE
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => handleRevokeKey(k.id)}
                      className="text-[11px] font-mono text-laser-crimson hover:text-red-400 font-bold px-2 py-1 bg-laser-crimson/10 border border-laser-crimson/20 rounded-sm transition-colors"
                    >
                      REVOKE
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
