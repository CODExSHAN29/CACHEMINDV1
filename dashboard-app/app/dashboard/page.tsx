"use client";

import { useState } from "react";
import {
  LayoutDashboard, Cpu, Zap, Activity, KeyRound, ArrowUpRight, ChevronUp, Bell, ShieldCheck,
  Banknote, Clock, TrendingUp, Layers
} from "lucide-react";

const modules = [
  { title: "Cache Hit Rate", val: "74.2%", sub: "Exact + Semantic Combined", delta: "+2.4% vs last 24h", color: "text-emerald-400", icon: ShieldCheck },
  { title: "Avg Latency (L2)", val: "1.18ms", sub: "P99 < 1.5ms", delta: "-0.42ms vs Direct LLM", color: "text-cyan-400", icon: Zap },
  { title: "Compute Reduced", val: "88.7%", sub: "Upstream Token Volume Cut", delta: "-12.3% MoM", color: "text-amber-400", icon: TrendingUp },
  { title: "Active Keys", val: "3 / 5", sub: "Scoped Inference Keys", delta: "1 revoked today", color: "text-indigo-400", icon: KeyRound },
  { title: "Monthly Tier", val: "Growth ($149)", sub: "5M Requests / Mo Quota", delta: "72% Usage", color: "text-rose-400", icon: Banknote },
];

export default function DashboardPage() {
  const [hover, setHover] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-200 font-mono selection:bg-indigo-500/30 pb-20">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-[#07090e]/90 border-b border-slate-800/60 backdrop-blur-2xl px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="font-display font-bold text-2xl text-slate-100 tracking-tight">Operations Command Center</h1>
          <p className="text-[10px] text-slate-500 tracking-widest uppercase">Real-Time Telemetry & Gateway Status</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="text-xs bg-indigo-950/60 border border-indigo-700/50 px-3 py-1.5 hover:bg-indigo-900/60 transition-colors text-indigo-300">PURGE CACHE</button>
          <button className="text-xs bg-emerald-950/60 border border-emerald-700/50 px-3 py-1.5 hover:bg-emerald-900/60 transition-colors text-emerald-300">WARM CACHE</button>
          <span className="text-[10px] font-mono bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-1">SYSTEM ONLINE</span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-8 space-y-12">
        {/* Module Cards */}
        <section className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {modules.map((m) => (
            <button
              key={m.title}
              onMouseEnter={() => setHover(m.title)}
              onMouseLeave={() => setHover(null)}
              className={`text-left relative bg-slate-950/80 border border-slate-800 p-5 transition-all hover:border-indigo-500/40 hover:-translate-y-0.5 shadow-xl ${hover === m.title ? "shadow-indigo-900/20" : ""}`}
            >
              <div className="flex items-start justify-between mb-4">
                <m.icon className={`w-8 h-8 ${m.color}`} />
                <ArrowUpRight className="w-3.5 h-3.5 text-slate-600" />
              </div>
              <div className={`text-2xl font-display font-bold ${m.color} mb-1 tracking-tight`}>{m.val}</div>
              <div className="text-[11px] text-slate-300 mb-0.5">{m.sub}</div>
              <div className="text-[10px] font-mono text-slate-500">{m.delta}</div>
            </button>
          ))}
        </section>

        {/* Live Query Stream */}
        <section className="border border-slate-800 bg-slate-950/60 backdrop-blur-md shadow-2xl">
          <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-800/60 bg-slate-900/30">
            <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <h2 className="font-display font-bold text-lg text-slate-100">Live Inference Stream</h2>
            <span className="text-[10px] text-slate-500 font-mono ml-auto">NODE: production-cluster-01 | TLS: 1.3</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] font-mono text-slate-300">
              <thead className="text-slate-500 bg-slate-900/50 border-b border-slate-800">
                <tr>
                  {["TIMESTAMP", "QUERY FINGERPRINT (L1)", "VECTOR MATCH (L2)", "LATENCY", "STATUS", "UPSTREAM"].map(h => (
                    <th key={h} className="text-left px-5 py-3 font-bold tracking-widest">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { ts: "15:42:01.112", fp: "sha256:e4c...a2b", vec: "cos_sim: 0.987", lat: "1.18ms", status: "HIT (L2)", upstream: "SKIPPED" },
                  { ts: "15:42:01.340", fp: "sha256:1a3...9f8", vec: "cos_sim: 0.912", lat: "2.01ms", status: "HIT (L1)", upstream: "SKIPPED" },
                  { ts: "15:42:02.011", fp: "sha256:8d2...f44", vec: "cos_sim: 0.104", lat: "842ms", status: "MISS", upstream: "GPT-4o (Direct)" },
                  { ts: "15:42:02.990", fp: "sha256:bc1...e11", vec: "cos_sim: 0.998", lat: "0.92ms", status: "HIT (L2)", upstream: "SKIPPED" },
                ].map(row => (
                  <tr key={row.ts} className="border-b border-slate-800/40 hover:bg-slate-900/40 transition-colors">
                    <td className="px-5 py-3 text-slate-500">{row.ts}</td>
                    <td className="px-5 py-3 font-mono text-indigo-300">{row.fp}</td>
                    <td className="px-5 py-3">{row.vec}</td>
                    <td className="px-5 py-3 text-emerald-400">{row.lat}</td>
                    <td className={`px-5 py-3 font-bold ${row.status.includes("MISS") ? "text-rose-400" : "text-emerald-400"}`}>{row.status}</td>
                    <td className="px-5 py-3 text-slate-500">{row.upstream}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Charts Area */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="border border-slate-800 bg-slate-950/60 p-6 shadow-xl">
            <div className="flex items-center gap-3 mb-6">
              <Zap className="w-5 h-5 text-indigo-400" />
              <h3 className="font-display font-bold text-lg">Cache Ratio Timeline (Last 30 Days)</h3>
            </div>
            <div className="h-48 flex items-end gap-2">
              {[68, 70, 72, 74, 73, 75, 76, 74, 78, 79, 77, 80, 82].map((v, i) => (
                <div key={i} className="flex-1 flex flex-col justify-end group">
                  <div className="text-[9px] text-center text-slate-500 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">{v}%</div>
                  <div
                    className="w-full bg-gradient-to-t from-indigo-950 to-indigo-500/60 border-t border-indigo-400/30 transition-all hover:from-indigo-900 hover:to-indigo-400"
                    style={{ height: `${v * 2.4}px` }}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="border border-slate-800 bg-slate-950/60 p-6 shadow-xl">
            <div className="flex items-center gap-3 mb-6">
              <Clock className="w-5 h-5 text-cyan-400" />
              <h3 className="font-display font-bold text-lg">Latency Savings (Direct vs CacheMind)</h3>
            </div>
            <div className="h-48 flex items-end gap-2">
              {[
                { direct: 840, cache: 1.2, label: "GPT-4o" },
                { direct: 1100, cache: 1.1, label: "Claude 3.5" },
                { direct: 420, cache: 0.9, label: "GPT-4o Mini" },
              ].map((bar, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-2">
                  <div className="w-full flex items-end gap-1 h-36">
                    <div className="flex-1 bg-rose-950/60 border border-rose-800/60" style={{ height: `${(bar.direct / 1200) * 100}%` }} />
                    <div className="flex-1 bg-emerald-950/60 border border-emerald-800/60" style={{ height: `${(bar.cache / 1200) * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-slate-400">{bar.label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Quick Access Grid */}
        <section>
          <h2 className="font-display font-bold text-xl mb-4">Quick Operations</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Vector Explorer", desc: "Inspect 384-D embeddings & clusters", href: "/cache", icon: Layers, color: "text-indigo-400" },
              { label: "Inference Arena", desc: "Live prompt testing with similarity", href: "/playground", icon: Zap, color: "text-cyan-400" },
              { label: "Telemetry", desc: "Cache hits, latency, token savings", href: "/analytics", icon: Activity, color: "text-amber-400" },
              { label: "Billing Portal", desc: "Stripe metered usage & tiers", href: "/billing", icon: Banknote, color: "text-rose-400" },
            ].map(link => (
              <a key={link.label} href={link.href} className="group bg-slate-950/80 border border-slate-800 p-5 hover:border-indigo-500/40 transition-all hover:-translate-y-0.5 shadow-xl">
                <div className="flex items-center justify-between mb-3">
                  <link.icon className={`w-6 h-6 ${link.color}`} />
                  <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-indigo-400 transition-colors" />
                </div>
                <h3 className="font-display font-bold text-base text-slate-100 mb-1">{link.label}</h3>
                <p className="text-[11px] font-mono text-slate-500">{link.desc}</p>
              </a>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
