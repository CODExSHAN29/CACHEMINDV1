"use client";

import React from "react";
import LandingNavbar from "@/components/landing/LandingNavbar";
import HeroConstellation from "@/components/three/HeroConstellation";
import VectorClusterVisualizer from "@/components/three/VectorClusterVisualizer";
import LiveBenchmark from "@/components/landing/LiveBenchmark";
import ArchitectureFlow from "@/components/landing/ArchitectureFlow";
import CodeShowcase from "@/components/landing/CodeShowcase";
import RoiCalculator from "@/components/landing/RoiCalculator";
import { ArrowDown, Sparkles, Zap, ShieldCheck, Shield } from "lucide-react";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[#07090e] text-slate-200 overflow-x-hidden selection:bg-indigo-500/30 selection:text-indigo-100">
      {/* ===== NAVBAR ===== */}
      <LandingNavbar />

      {/* ===== HERO ===== */}
      <section id="hero" className="relative h-[92vh] flex items-center justify-center overflow-hidden">
        <HeroConstellation />
        <div className="absolute inset-0 z-10 bg-gradient-to-b from-[#07090e]/60 via-transparent to-[#07090e] pointer-events-none" />

        <div className="relative z-20 text-center px-6 max-w-5xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-900/60 border border-slate-700/60 text-xs font-mono text-slate-300 mb-6 shadow-inner shadow-indigo-950/20">
            <Zap className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>ENTERPRISE SEMANTIC CACHE GATEWAY v1.4</span>
          </div>

          <h1 className="font-display font-extrabold text-6xl sm:text-7xl lg:text-9xl tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-slate-50 via-indigo-100 to-slate-500 leading-[0.85] mb-6 drop-shadow-2xl">
            SUB-MILLISECOND<br />
            <span className="italic font-light">SEMANTIC</span> CACHING
          </h1>

          <p className="text-sm sm:text-base font-mono text-slate-400 leading-relaxed max-w-2xl mx-auto mb-10 tracking-tight">
            CacheMind intercepts repeat, rephrased, and paraphrased LLM queries at the gateway using deterministic SHA-256 exact caching and 384D FastEmbed BGE-Small semantic vector search — before they reach expensive upstream compute.
          </p>

          <div className="flex flex-wrap justify-center gap-3 mb-8">
            <a href="#interactive-demo" className="btn-primary text-xs font-mono flex items-center gap-2 shadow-xl shadow-indigo-900/40">
              <Sparkles className="w-4 h-4" />
              EXPLORE LIVE BENCHMARK
            </a>
            <a href="#pricing" className="text-xs font-mono px-6 py-3 bg-slate-900/60 border border-slate-700 text-slate-300 hover:border-indigo-500/60 hover:text-indigo-300 transition-all shadow-inner shadow-indigo-950/10">
              VIEW PRICING
            </a>
          </div>

          <div className="flex flex-wrap justify-center gap-6 md:gap-12 text-xs font-mono text-slate-500">
            <div className="flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-400" /> <span>88% COMPUTE REDUCTION</span></div>
            <div className="flex items-center gap-2"><Zap className="w-4 h-4 text-cyan-400" /> <span>&lt; 1.5ms P99 LATENCY</span></div>
            <div className="flex items-center gap-2"><Shield className="w-4 h-4 text-indigo-400" /> <span>100% DETERMINISTIC</span></div>
          </div>
        </div>
      </section>

      {/* ===== BENCHMARKS ===== */}
      <section id="benchmarks" className="py-24 px-4 lg:px-8 max-w-7xl mx-auto">
        <LiveBenchmark />
      </section>

      {/* ===== ARCHITECTURE ===== */}
      <section id="architecture" className="py-24 px-4 lg:px-8 max-w-7xl mx-auto">
        <ArchitectureFlow />
      </section>

      {/* ===== INTERACTIVE DEMO / 3D VECTOR SPACE ===== */}
      <section id="interactive-demo" className="py-24 px-4 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <span className="label-caps text-indigo-400 mb-2 block">VECTOR SPACE VISUALIZER</span>
          <h2 className="font-display font-bold text-4xl sm:text-5xl text-slate-100 tracking-tight mb-3">Interactive Semantic Clustering</h2>
          <p className="text-xs font-mono text-slate-400 max-w-xl mx-auto leading-relaxed">
            Explore how CacheMind maps queries into a 384-dimensional space using FastEmbed BGE-Small ONNX embeddings and compares cosine similarity to determine cache hits.
          </p>
        </div>

        <VectorClusterVisualizer />
      </section>

      {/* ===== CODE SHOWCASE ===== */}
      <section id="code-showcase" className="py-24 px-4 lg:px-8 max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <span className="label-caps text-cyan-400 mb-2 block">SDK INTEGRATIONS</span>
          <h2 className="font-display font-bold text-4xl text-slate-100 tracking-tight">One Line. Zero Changes.</h2>
        </div>
        <CodeShowcase />
      </section>

      {/* ===== ROI CALCULATOR ===== */}
      <section id="roi-calculator" className="py-24 px-4 lg:px-8 max-w-7xl mx-auto">
        <RoiCalculator />
      </section>

      {/* ===== PRICING ===== */}
      <section id="pricing" className="py-24 px-4 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <span className="label-caps text-emerald-400 mb-2 block">TRANSPARENT PRICING</span>
          <h2 className="font-display font-bold text-4xl sm:text-5xl text-slate-100 tracking-tight mb-4">Scale As You Grow</h2>
          <p className="text-xs font-mono text-slate-400 max-w-lg mx-auto">Developer tier starts at $0 with full semantic caching capabilities. No hidden overage fees.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { title: "Developer", price: "$0", period: "forever free", features: ["500K requests / month", "L1 Exact Cache", "L2 Semantic Search", "3 API Keys", "Community Support"], highlight: false },
            { title: "Growth", price: "$149", period: "/ month", features: ["5M requests / month", "L1 + L2 Full Access", "Custom Volatility Policies", "Real-Time Telemetry", "Priority Email Support", "Stripe Portal"], highlight: true },
            { title: "Enterprise", price: "$899", period: "/ month", features: ["Unlimited Requests", "Dedicated Cluster", "On-Prem / Private Cloud", "SSO / SAML", "Dedicated Engineer", "Custom Guardrails"], highlight: false },
          ].map((tier) => (
            <div key={tier.title} className={`relative p-8 border shadow-2xl backdrop-blur-xl ${tier.highlight ? "bg-slate-900/90 border-indigo-500/40 shadow-indigo-500/10 scale-[1.02]" : "bg-slate-950/60 border-slate-800/60"}`}>
              {tier.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-indigo-600 text-white text-[10px] font-mono px-3 py-0.5 font-bold tracking-widest uppercase">Most Popular</div>
              )}
              <h3 className="font-display font-bold text-xl text-slate-100 mb-2">{tier.title}</h3>
              <div className="flex items-baseline gap-1 mb-6">
                <span className="font-display font-bold text-4xl text-emerald-400">{tier.price}</span>
                <span className="text-xs font-mono text-slate-500">{tier.period}</span>
              </div>
              <ul className="space-y-3 mb-8">
                {tier.features.map((f) => (
                  <li key={f} className="text-xs font-mono text-slate-300 flex items-center gap-2">
                    <span className="w-1 h-1 bg-indigo-400 rounded-full shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              <a href="#" className={`block text-center text-xs font-mono py-3 border transition-colors ${tier.highlight ? "bg-indigo-600 border-indigo-500 text-white hover:bg-indigo-500" : "bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-600"}`}>
                {tier.price === "$0" ? "GET API KEY" : "SELECT PLAN"}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="border-t border-slate-800 bg-[#07090e] py-12 px-6 lg:px-8">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-10">
          <div>
            <div className="font-display font-bold text-xl text-slate-100 mb-3 tracking-tight">CacheMind</div>
            <p className="text-xs font-mono text-slate-500 leading-relaxed">Precision semantic caching gateway for AI applications. Sub-millisecond L1 exact and L2 semantic hit detection.</p>
          </div>
          <div>
            <h4 className="text-xs font-mono font-bold text-indigo-400 mb-3 uppercase tracking-widest">Product</h4>
            <ul className="space-y-2 text-xs font-mono text-slate-400">
              <li><a href="#benchmarks" className="hover:text-slate-200">Benchmarks</a></li>
              <li><a href="#architecture" className="hover:text-slate-200">Architecture</a></li>
              <li><a href="#" className="hover:text-slate-200">Documentation</a></li>
              <li><a href="#" className="hover:text-slate-200">Changelog</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-mono font-bold text-cyan-400 mb-3 uppercase tracking-widest">Console</h4>
            <ul className="space-y-2 text-xs font-mono text-slate-400">
              <li><a href="/dashboard" className="hover:text-slate-200">Dashboard</a></li>
              <li><a href="/cache" className="hover:text-slate-200">Cache Explorer</a></li>
              <li><a href="/playground" className="hover:text-slate-200">Inference Arena</a></li>
              <li><a href="/analytics" className="hover:text-slate-200">Analytics</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-mono font-bold text-emerald-400 mb-3 uppercase tracking-widest">Status</h4>
            <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 mb-1">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" /> All Systems Operational
            </div>
            <div className="text-xs font-mono text-slate-500">Uptime: 99.99%</div>
          </div>
        </div>
        <div className="max-w-7xl mx-auto mt-10 pt-6 border-t border-slate-900 flex flex-col md:flex-row items-center justify-between gap-4 text-[11px] font-mono text-slate-600">
          <span>CacheMind Inc. All rights reserved.</span>
          <div className="flex gap-6">
            <a href="#" className="hover:text-slate-400">Privacy</a>
            <a href="#" className="hover:text-slate-400">Terms</a>
            <a href="#" className="hover:text-slate-400">GitHub</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
