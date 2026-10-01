"use client";
import { useState, useEffect, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { PlaygroundResponse } from "@/lib/types";
import PageHeader from "@/components/PageHeader";
export default function PlaygroundPage() {
  const { activeWorkspace, projects } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [tags, setTags] = useState("");
  const [namespace, setNamespace] = useState("");
  const [response, setResponse] = useState<PlaygroundResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const current = useRef(activeWorkspace?.id); current.current = activeWorkspace?.id;
  useEffect(() => { setResponse(null); setError(""); }, [activeWorkspace?.id]);
  async function run() {
    const workspace = activeWorkspace?.id;
    setBusy(true); setResponse(null); setError("");
    try {
      const data = await api.sendPlaygroundInference(prompt.trim(), model.trim(), tags.split(",").map(t => t.trim()).filter(Boolean), namespace.trim() || undefined);
      if (current.current === workspace) setResponse(data);
    } catch (e) { if (current.current === workspace) setError(e instanceof Error ? e.message : "Inference failed."); }
    finally { setBusy(false); }
  }
  return <div><PageHeader index="04 / Playground" title="Inference Laboratory" description="Send a request through the gateway and inspect the returned response metadata." /><div className="grid grid-cols-1 lg:grid-cols-2 gap-6"><section className="hairline-panel"><div className="panel-heading">Request composer</div><form className="p-6 space-y-5" onSubmit={e => { e.preventDefault(); run(); }}><p className="text-xs text-on-surface-variant leading-6">Session inference uses the workspace’s default project{projects[0]?.name ? ` (${projects[0].name})` : ""}. To target another project, use its API key from your application.</p><label htmlFor="model" className="label-caps block">Model</label><input id="model" className="input-field w-full" required value={model} onChange={e => setModel(e.target.value)} /><label htmlFor="prompt" className="label-caps block">User prompt</label><textarea id="prompt" className="input-field w-full" rows={8} placeholder="Enter a request to test cache reuse." required value={prompt} onChange={e => setPrompt(e.target.value)} /><div className="grid grid-cols-1 sm:grid-cols-2 gap-4"><div><label className="label-caps block mb-2" htmlFor="tags">Tags / CSV</label><input id="tags" className="input-field w-full" value={tags} onChange={e => setTags(e.target.value)} /></div><div><label className="label-caps block mb-2" htmlFor="namespace">Namespace</label><input id="namespace" className="input-field w-full" value={namespace} onChange={e => setNamespace(e.target.value)} /></div></div><button className="btn-primary w-full" disabled={busy}>{busy ? "Routing request…" : "Run request"}</button></form></section><section className="hairline-panel"><div className="panel-heading">Response / observation</div>{error ? <div className="alert-error m-6" role="alert">{error}</div> : busy ? <div className="state-panel" role="status">Awaiting gateway response…</div> : !response ? <div className="state-panel"><h3>AWAITING REQUEST</h3><p>Run a request to inspect its response, cache path, and measured roundtrip latency.</p></div> : <div className="p-6 space-y-6"><div className="flex justify-between gap-4"><span className="badge-pill status-badge" data-state={response.cache_status}>{response.cache_status ?? "PATH UNAVAILABLE"}</span><button className="text-primary-bright text-xs" onClick={async () => { try { await navigator.clipboard.writeText(response.choices?.[0]?.message?.content ?? ""); } catch { setError("Clipboard unavailable. Select the response and copy it manually."); } }}>Copy response</button></div><pre className="surface-inset p-5 text-sm leading-7 whitespace-pre-wrap break-words max-h-96 overflow-auto">{response.choices?.[0]?.message?.content ?? "No text content returned."}</pre><dl className="grid grid-cols-2 gap-6 text-xs font-mono">{[["Roundtrip latency", response.latency_ms == null ? undefined : `${response.latency_ms} ms`], ["Similarity", response.semantic_score?.toFixed(4)], ["Tokens saved", response.tokens_saved], ["Est. cost saved", response.cost_saved_usd == null ? undefined : `$${response.cost_saved_usd.toFixed(6)}`], ["Model", response.model], ["Request ID", response.id]].map(([label, value]) => <div key={label}><dt className="label-caps mb-2">{label}</dt><dd className="break-all">{value ?? "Unavailable"}</dd></div>)}</dl><div className="surface-inset p-4"><h3 className="label-caps mb-3">Observed result path</h3><p className="font-mono text-xs text-primary-bright">{response.cache_status === "EXACT_HIT" ? "REQUEST → L1 EXACT → RESPONSE" : response.cache_status === "SEMANTIC_HIT" || response.cache_status === "L2_HIT" ? "REQUEST → L2 SEMANTIC → RESPONSE" : response.cache_status === "CACHE_MISS" || response.cache_status === "MISS" ? "REQUEST → UPSTREAM → RESPONSE" : "Path metadata unavailable"}</p></div></div>}</section></div></div>;
}
