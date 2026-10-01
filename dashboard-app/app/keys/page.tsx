"use client";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { useScopedData } from "@/lib/useScopedData";
import PageHeader from "@/components/PageHeader";
import ConfirmDialog from "@/components/ConfirmDialog";
import { DataState } from "@/components/Telemetry";
const loadKeys = (_tenant: string, project?: string) => project ? api.listAPIKeys(project) : Promise.resolve([]);
export default function KeysPage() {
  const { activeProject, activeWorkspace } = useAuth();
  const [refresh, setRefresh] = useState(0);
  const keys = useScopedData(loadKeys, refresh);
  const [name, setName] = useState("");
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [revoke, setRevoke] = useState<string | null>(null);
  const scope = `${activeWorkspace?.id}/${activeProject?.id}`;
  const current = useRef(scope); current.current = scope;
  useEffect(() => { setRawKey(null); setRevoke(null); setError(""); }, [scope]);
  async function create() {
    if (!activeProject) return;
    const requestScope = scope;
    setBusy(true); setError(""); setCopied(false);
    try {
      const result = await api.createAPIKey(activeProject.id, name.trim(), "admin");
      if (current.current !== requestScope) return;
      if (!result.raw_key) throw new Error("The gateway did not return a credential.");
      setRawKey(result.raw_key); setName(""); setRefresh(v => v + 1);
    } catch (e) { if (current.current === requestScope) setError(e instanceof Error ? e.message : "Key creation failed."); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!revoke) return;
    setBusy(true); setError("");
    try { await api.revokeAPIKey(revoke); setRevoke(null); setRefresh(v => v + 1); }
    catch (e) { setError(e instanceof Error ? e.message : "Revocation failed."); }
    finally { setBusy(false); }
  }
  return <div><PageHeader index="05 / Keys" title="Project Credentials" description="Create and revoke gateway credentials. Each secret is revealed once." />{error && <div className="alert-error" role="alert">{error}</div>}<section className="hairline-panel mb-6"><div className="panel-heading">Create project key<span className="text-on-surface-faint">{activeProject?.name ?? "Select a project"}</span></div><form className="p-6" onSubmit={e => { e.preventDefault(); create(); }}><label className="label-caps block mb-3" htmlFor="key-name">Credential name</label><div className="flex flex-col sm:flex-row gap-3"><input id="key-name" className="input-field flex-1 min-w-0" required placeholder="e.g. development-service" value={name} onChange={e => setName(e.target.value)} /><button className="btn-primary" disabled={busy || !activeProject || !name.trim()}>{busy ? "Creating…" : "Create key"}</button></div></form></section><section className="hairline-panel"><div className="panel-heading">Credential registry<span className="text-on-surface-faint">{keys.data?.length ?? "—"} records</span></div>{keys.loading || keys.error ? <DataState loading={keys.loading} error={keys.error} retry={() => setRefresh(v => v + 1)} /> : !keys.data?.length ? <div className="state-panel"><h3>NO KEYS PROVISIONED</h3><p>Create a credential for the selected project to send requests through the gateway.</p></div> : <div className="overflow-x-auto"><table className="data-table"><thead className="table-header-row"><tr>{["Name", "Prefix", "Role", "Created", "Last used", "Status", "Action"].map(label => <th className="table-header-cell" key={label}>{label}</th>)}</tr></thead><tbody>{keys.data.map(key => <tr key={key.id}><td>{key.name}</td><td className="text-primary-bright">{key.key_prefix}…</td><td>{key.role}</td><td>{new Date(key.created_at).toLocaleDateString()}</td><td>{key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never"}</td><td>{key.is_active ? "ACTIVE" : "REVOKED"}</td><td><button disabled={busy || !key.is_active} className="text-red-300" onClick={() => setRevoke(key.id)}>Revoke</button></td></tr>)}</tbody></table></div>}</section><p className="text-xs text-on-surface-variant leading-7 mt-6 max-w-2xl">Keep API keys in your application environment. Raw credentials are never stored in browser storage. A lost key must be revoked and replaced.</p>{rawKey && <ConfirmDialog title="Secret generated" onClose={() => setRawKey(null)}><p className="text-sm text-on-surface-variant mt-4">This credential will not be shown again. Copy it before closing.</p><code>{rawKey}</code><div className="flex flex-wrap gap-3"><button className="btn-primary" onClick={async () => { try { await navigator.clipboard.writeText(rawKey); setCopied(true); } catch { setError("Clipboard unavailable. Select and copy the secret manually."); } }}>{copied ? "Copied" : "Copy secret"}</button><button className="btn-secondary" onClick={() => setRawKey(null)}>Done</button></div></ConfirmDialog>}{revoke && <ConfirmDialog title="Revoke credential" onClose={() => setRevoke(null)}><p className="text-sm text-on-surface-variant my-6">Applications using this key will lose gateway access. This action cannot be undone.</p><div className="flex gap-3"><button className="btn-secondary" onClick={() => setRevoke(null)}>Cancel</button><button disabled={busy} className="btn-primary" onClick={remove}>{busy ? "Revoking…" : "Revoke key"}</button></div></ConfirmDialog>}</div>;
}
