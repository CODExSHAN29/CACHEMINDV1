"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { APIKeyInfo, ProjectInfo, TenantInfo } from "@/lib/types";

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
      toast.error("Please enter a key name");
      return;
    }
    try {
      const res = await api.createAPIKey(selectedProject, newKeyName.trim(), newKeyRole);
      toast.success("API key created successfully!");
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
    if (!confirm("Are you sure you want to revoke this API key? This action is irreversible.")) {
      return;
    }
    try {
      await api.revokeAPIKey(keyId);
      toast.success("API key revoked");
      refreshData();
    } catch (e: any) {
      toast.error(`Revocation failed: ${e.message}`);
    }
  };

  const handleCreateTenant = async () => {
    if (!newTenantName.trim()) return;
    try {
      await api.createTenant(newTenantName.trim());
      toast.success("Tenant created");
      setNewTenantName("");
      refreshData();
    } catch (e: any) {
      toast.error(`Failed to create tenant: ${e.message}`);
    }
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      await api.createProject(selectedTenant, newProjectName.trim());
      toast.success("Project created");
      setNewProjectName("");
      refreshData();
    } catch (e: any) {
      toast.error(`Failed to create project: ${e.message}`);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">API Keys & Multi-Tenant Management</h2>
        <p className="text-sm text-gray-400 mt-1">
          Provision tenants, isolate projects, and issue cryptographically hashed API keys.
        </p>
      </div>

      {/* Selector & Provisioning Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Tenant Box */}
        <div className="bg-dark-card border border-dark-border rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span>🏢</span> Select Tenant
            </h3>
            <span className="text-xs text-gray-400">{tenants.length} tenants</span>
          </div>
          <select
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs font-mono"
          >
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.id})
              </option>
            ))}
          </select>
          <div className="flex gap-2 pt-2">
            <input
              type="text"
              placeholder="New Tenant Name..."
              value={newTenantName}
              onChange={(e) => setNewTenantName(e.target.value)}
              className="flex-1 bg-dark-bg border border-dark-border rounded-lg px-3 py-1.5 text-xs text-white"
            />
            <button
              onClick={handleCreateTenant}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg font-medium"
            >
              Add Tenant
            </button>
          </div>
        </div>

        {/* Project Box */}
        <div className="bg-dark-card border border-dark-border rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span>📁</span> Select Project
            </h3>
            <span className="text-xs text-gray-400">{projects.length} projects</span>
          </div>
          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs font-mono"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.id})
              </option>
            ))}
          </select>
          <div className="flex gap-2 pt-2">
            <input
              type="text"
              placeholder="New Project Name..."
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="flex-1 bg-dark-bg border border-dark-border rounded-lg px-3 py-1.5 text-xs text-white"
            />
            <button
              onClick={handleCreateProject}
              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-lg font-medium"
            >
              Add Project
            </button>
          </div>
        </div>
      </div>

      {/* Key Creation Form */}
      <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-dark-border">
          <span className="text-xl">🔑</span>
          <h3 className="text-base font-semibold text-white">Issue New Scoped API Key</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Key Description / Name</label>
            <input
              type="text"
              placeholder="e.g. Production Backend Service"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Role / Scope</label>
            <select
              value={newKeyRole}
              onChange={(e) => setNewKeyRole(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white text-xs font-mono"
            >
              <option value="inference">inference (Chat & Streaming)</option>
              <option value="read_only">read_only (Analytics & Metrics)</option>
              <option value="admin">admin (Full Project Control)</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleCreateKey}
              className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg transition-colors"
            >
              Generate Live Key
            </button>
          </div>
        </div>

        {createdRawKey && (
          <div className="mt-4 p-4 bg-emerald-950/40 border border-emerald-800/60 rounded-lg space-y-1">
            <p className="text-xs text-emerald-300 font-semibold">
              ⚠️ Save this API key now. It will not be shown again:
            </p>
            <div className="flex items-center justify-between font-mono text-xs text-white bg-dark-bg p-2 rounded border border-dark-border">
              <span>{createdRawKey}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(createdRawKey);
                  toast.success("Key copied to clipboard!");
                }}
                className="text-xs text-blue-400 hover:text-blue-300 underline"
              >
                Copy
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Existing Keys Table */}
      <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4">
        <h3 className="text-base font-semibold text-white">Active API Keys</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-300">
            <thead className="bg-dark-bg/60 text-xs text-gray-400 uppercase tracking-wider border-b border-dark-border">
              <tr>
                <th className="py-3 px-4">Name</th>
                <th className="py-3 px-4">Key Prefix</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Created</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border/60">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-dark-hover/50">
                  <td className="py-3.5 px-4 font-medium text-white">{k.name}</td>
                  <td className="py-3.5 px-4 font-mono text-xs text-gray-400">{k.key_prefix}...</td>
                  <td className="py-3.5 px-4 font-mono text-xs">
                    <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-400 border border-blue-800/40">
                      {k.role}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-xs text-gray-400">
                    {new Date(k.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="text-xs text-emerald-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                      Active
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <button
                      onClick={() => handleRevokeKey(k.id)}
                      className="text-xs text-rose-400 hover:text-rose-300 font-medium"
                    >
                      Revoke
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
