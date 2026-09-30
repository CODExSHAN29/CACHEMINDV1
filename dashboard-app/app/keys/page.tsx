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
      {/* Precision Dossier Header */}
      <div className="bg-surface border border-outline p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge-pill bg-primary text-white border-primary">
              SYS.ZONE // 04
            </span>
            <span className="text-on-surface-variant font-mono text-xs">
              :: [IAM & MULTI-TENANT ISOLATION PLANE]
            </span>
          </div>
          <h1 className="text-2xl font-display font-bold text-on-surface uppercase tracking-tight mt-2">
            API Keys & Multi-Tenant Access Control
          </h1>
          <p className="text-xs font-sans text-on-surface-variant mt-1 max-w-3xl">
            Provision tenant partitions, isolate project namespaces, and issue SHA-256 hashed API keys with granular role permissions.
          </p>
        </div>
      </div>

      {/* Tenant / Project Provisioning Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Tenant Box */}
        <div className="bg-surface border border-outline p-5 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Building className="w-4 h-4 text-primary" />
              <h2 className="text-xs font-bold text-on-surface uppercase tracking-wider">
                TENANT PARTITIONS
              </h2>
            </div>
            <span className="text-[10px] font-mono text-on-surface-variant bg-surface-dim px-2 py-0.5 border border-outline-variant">
              COUNT: [{tenants.length}]
            </span>
          </div>

          <select
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            className="w-full bg-surface-dim border border-outline px-3 py-2 text-on-surface font-mono text-xs focus:outline-none focus:border-primary"
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
              className="flex-1 bg-surface-dim border border-outline px-3 py-1.5 text-xs text-on-surface font-mono focus:outline-none focus:border-primary"
            />
            <button
              onClick={handleCreateTenant}
              className="px-3 py-1.5 bg-surface-dim hover:bg-blue-50 border border-outline hover:border-primary text-primary text-xs font-bold flex items-center gap-1.5 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>PROVISION</span>
            </button>
          </div>
        </div>

        {/* Project Box */}
        <div className="bg-surface border border-outline p-5 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <FolderGit2 className="w-4 h-4 text-secondary" />
              <h2 className="text-xs font-bold text-on-surface uppercase tracking-wider">
                PROJECT WORKSPACES
              </h2>
            </div>
            <span className="text-[10px] font-mono text-on-surface-variant bg-surface-dim px-2 py-0.5 border border-outline-variant">
              COUNT: [{projects.length}]
            </span>
          </div>

          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            className="w-full bg-surface-dim border border-outline px-3 py-2 text-on-surface font-mono text-xs focus:outline-none focus:border-secondary"
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
              className="flex-1 bg-surface-dim border border-outline px-3 py-1.5 text-xs text-on-surface font-mono focus:outline-none focus:border-secondary"
            />
            <button
              onClick={handleCreateProject}
              className="px-3 py-1.5 bg-surface-dim hover:bg-blue-50 border border-outline hover:border-secondary text-secondary text-xs font-bold flex items-center gap-1.5 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>PROVISION</span>
            </button>
          </div>
        </div>
      </div>

      {/* Key Generation Form */}
      <div className="bg-surface border border-outline p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
          <div className="flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-primary" />
            <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
              ISSUE LIVE SCOPED API TOKEN
            </h2>
          </div>
          <span className="text-[10px] font-mono text-on-surface-variant bg-surface-dim px-2 py-0.5 border border-outline-variant">
            TARGET: [{selectedProject}]
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
          <div className="space-y-1">
            <label className="label-caps">KEY IDENTIFIER / NAME</label>
            <input
              type="text"
              placeholder="e.g. PROD-API-GATEWAY-INFERENCE"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              className="w-full bg-surface-dim border border-outline px-3 py-2 text-on-surface text-xs font-mono focus:outline-none focus:border-primary"
            />
          </div>

          <div className="space-y-1">
            <label className="label-caps">ROLE / PERMISSION SCOPE</label>
            <select
              value={newKeyRole}
              onChange={(e) => setNewKeyRole(e.target.value)}
              className="w-full bg-surface-dim border border-outline px-3 py-2 text-on-surface text-xs font-mono focus:outline-none focus:border-primary"
            >
              <option value="inference">inference (Chat, Streaming, Normalization)</option>
              <option value="read_only">read_only (Metrics, Telemetry Audit)</option>
              <option value="admin">admin (Full Cluster Control Plane)</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleCreateKey}
              className="btn-solid w-full py-2.5 bg-primary text-white border-primary hover:bg-blue-800 font-mono font-bold text-xs flex items-center justify-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>GENERATE SECRET KEY</span>
            </button>
          </div>
        </div>

        {createdRawKey && (
          <div className="mt-3 p-4 bg-emerald-50 border border-emerald-300 space-y-2">
            <div className="flex items-center gap-2 text-xs font-mono text-emerald-800 font-bold">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>SECRET KEY GENERATED — STORE IMMEDIATELY:</span>
            </div>
            <div className="flex items-center justify-between font-mono text-xs text-on-surface bg-white p-2.5 border border-emerald-300">
              <span className="text-emerald-700 font-bold select-all">{createdRawKey}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(createdRawKey);
                  toast.success("Secret API key copied to clipboard.");
                }}
                className="flex items-center gap-1 text-[11px] font-mono text-on-surface px-2.5 py-1 bg-surface-dim border border-outline hover:border-primary transition-colors font-bold"
              >
                <Copy className="w-3 h-3" />
                <span>COPY</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Active API Keys Table */}
      <div className="bg-surface border border-outline p-5 space-y-3">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-primary" />
            <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
              ACTIVE ACCESS TOKENS IN REGISTRY
            </h2>
          </div>
          <span className="text-[10px] font-mono text-on-surface-variant bg-surface-dim px-2 py-0.5 border border-outline-variant">
            TOTAL: [{keys.length}]
          </span>
        </div>

        <div className="overflow-x-auto border border-outline">
          <table className="w-full text-left text-xs font-mono text-on-surface">
            <thead className="bg-surface-dim text-[10px] text-on-surface-variant uppercase tracking-wider border-b border-outline">
              <tr>
                <th className="py-2.5 px-4 font-bold">IDENTIFIER</th>
                <th className="py-2.5 px-4 font-bold">PREFIX</th>
                <th className="py-2.5 px-4 font-bold">SCOPE</th>
                <th className="py-2.5 px-4 font-bold">CREATED</th>
                <th className="py-2.5 px-4 font-bold">STATUS</th>
                <th className="py-2.5 px-4 text-right font-bold">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-surface-dim transition-colors">
                  <td className="py-3 px-4 font-bold text-on-surface">{k.name}</td>
                  <td className="py-3 px-4 text-on-surface-variant">{k.key_prefix}...</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 bg-blue-50 text-primary border border-blue-200 text-[10px] font-bold uppercase">
                      {k.role}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-on-surface-variant tabular-nums">
                    {new Date(k.created_at).toISOString().substring(0, 10)}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-emerald-700 text-[11px] font-bold flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 bg-emerald-600"></span>
                      ACTIVE
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => handleRevokeKey(k.id)}
                      className="text-[11px] font-mono text-red-600 hover:text-red-700 font-bold px-2.5 py-1 bg-red-50 border border-red-200 transition-colors"
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
