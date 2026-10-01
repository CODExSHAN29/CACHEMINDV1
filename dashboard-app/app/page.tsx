"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowUpRight, Square } from "lucide-react";
const CacheRibbon = dynamic(() => import("@/components/three/CacheRibbon"), { ssr: false });
const source = "https://github.com/CODExSHAN29/CACHEMINDV1";
const modes = ["Topological mesh", "Attention flux", "Latent surface"];

export default function LandingPage() {
  const [tension, setTension] = useState(0.437);
  const [mode, setMode] = useState(0);
  return <main>
    <nav className="public-nav" aria-label="Main navigation">
      <Link href="/" className="wordmark"><Square fill="currentColor" /><span>CACHEMIND</span></Link>
      <div className="public-nav-links"><a href="#product">Product</a><a href="#architecture">Architecture</a><a href="#benchmarks">Benchmarks</a><a href={`${source}#readme`}>Docs</a><a href={source}>GitHub <ArrowUpRight size={12} className="inline" /></a></div>
      <div className="public-nav-actions"><Link href="/login">Sign in</Link><Link href="/signup" className="btn-primary">Try now <ArrowUpRight size={14} /></Link></div>
    </nav>
    <section className="hero-stage" aria-labelledby="hero-title">
      <CacheRibbon tension={tension} mode={mode} />
      <div className="hero-meta"><p>A memory layer for repeated intelligence.<br />Exact matches. Semantic retrieval.<br />Measured at the gateway.</p><p>Why generate the same answer twice?<br /><span className="text-white">Reuse what your application already knows.</span></p></div>
      <div className="hero-title"><div className="section-index">Semantic retrieval fabric</div><h1 id="hero-title" className="editorial">The Shape <em>of</em><strong>CACHE</strong></h1><div className="hero-caption"><span>01 / EXACT MATCHING</span><span>02 / SEMANTIC RETRIEVAL</span><span>03 / MEASURABLE REUSE</span></div></div>
      <div className="hero-controls">
        <div className="shape-control"><label htmlFor="ribbon-tension">SHAPE TENSION <output>{tension.toFixed(3)}</output></label><input id="ribbon-tension" type="range" min="0" max="1" step="0.001" value={tension} onChange={e => setTension(Number(e.target.value))} /><small>ABSTRACT GEOMETRY / NOT LIVE TELEMETRY</small></div>
        <div className="shape-tabs" aria-label="Geometry modes">{modes.map((label, index) => <button key={label} aria-pressed={mode === index} onClick={() => { setMode(index); setTension([0.437, 0.814, 0.024][index]); }}>0{index + 1}. {label}</button>)}</div>
        <Link href="/signup" className="btn-secondary hero-enter">Enter the gateway <ArrowUpRight size={16} /></Link>
      </div>
    </section>
    <div className="colophon"><span>PREMISE / REUSE BEFORE RECOMPUTE</span><span>VISUAL / PROCEDURAL WEBGL STUDY</span><span>CACHEMIND / LLM INFRASTRUCTURE</span></div>
    <section id="product" className="landing-section"><div className="section-index">01 / The memory layer</div><h2 className="editorial">An answer worth keeping.<br /><em>A request worth avoiding.</em></h2><p>CacheMind sits between your application and its LLM provider. It checks exact requests first, then evaluates semantic similarity before routing cache misses upstream. Inspect reuse, token savings, and latency in one workspace.</p><div className="mt-8"><Link href="/signup" className="btn-primary">Create your workspace <ArrowUpRight size={14} /></Link></div></section>
    <section id="architecture" className="landing-section"><div className="section-index">02 / Architecture</div><h2 className="editorial">A deliberate path<br />through memory.</h2><div className="architecture-grid">{[{name:"Exact recovery",body:"Canonical request fingerprints resolve repeated requests from the exact cache, scoped to the authenticated tenant and project."},{name:"Semantic retrieval",body:"Embedding similarity evaluates eligible requests against stored responses. Guardrails and cache policy determine whether reuse is allowed."},{name:"Upstream routing",body:"Requests that cannot be safely served from memory continue to the model provider. Observed results feed the gateway’s telemetry."}].map((item, index) => <article key={item.name}><div className="section-index">L{index + 1} / {index === 2 ? "PROVIDER" : "CACHE"}</div><h3>{item.name}</h3><p>{item.body}</p></article>)}</div></section>
    <section id="integration" className="landing-section"><div className="section-index">03 / Integration</div><h2 className="editorial">A familiar interface.<br />A different request path.</h2><p>Use an OpenAI-compatible client with your gateway URL and a project API key. Keep credentials in your application environment.</p><pre className="integration-code surface-inset"><code>{`from openai import OpenAI\nimport os\n\nclient = OpenAI(\n    base_url=os.environ["CACHEMIND_BASE_URL"],\n    api_key=os.environ["CACHEMIND_API_KEY"],\n)\n\nresponse = client.chat.completions.create(\n    model="gpt-4o-mini",\n    messages=[{"role": "user", "content": "Explain semantic caching."}],\n)`}</code></pre><a className="btn-secondary mt-6" href={`${source}/blob/main/docs/real_data_setup.md`}>Read integration guide <ArrowUpRight size={14} /></a></section>
    <section id="benchmarks" className="landing-section"><div className="section-index">04 / Evidence</div><h2 className="editorial">Measure the workload.<br />Then judge the savings.</h2><p>Hit rate and latency depend on request repetition, cache policy, model, and deployment. Run the repository’s benchmark against your own gateway and inspect actual results in the console.</p><div className="flex flex-wrap gap-4 mt-8"><a href={`${source}/blob/main/scripts/benchmark_latency.py`} className="btn-secondary">Benchmark source <ArrowUpRight size={14} /></a><Link href="/login" className="btn-secondary">Open telemetry <ArrowUpRight size={14} /></Link></div></section>
    <footer className="landing-footer"><Link href="/" className="wordmark">CACHEMIND</Link><span>REUSE BEFORE RECOMPUTE.</span><a href={source}>SOURCE / GITHUB <ArrowUpRight size={12} className="inline" /></a></footer>
  </main>;
}
