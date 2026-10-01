"use client";

import React, { useState } from "react";
import { Terminal, Copy, Check, Code, Sparkles, FileCode, Cpu } from "lucide-react";

interface CodeSnippet {
  language: string;
  tabLabel: string;
  filename: string;
  code: string;
  highlight: string;
}

const SNIPPETS: CodeSnippet[] = [
  {
    language: "python",
    tabLabel: "Python SDK",
    filename: "main.py",
    highlight: "Full semantic cache auto-lookup with fallback",
    code: `from cachemind import CacheMindClient

# Initialize CacheMind high-performance client
client = CacheMindClient(
    api_key="cm_live_your_project_key_here",
    similarity_threshold=0.92, # FastEmbed 384D BGE-Small Cosine
    tenant_id="your_workspace_id"
)

# Semantic-aware completion call (< 1.5ms on hit)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a quantitative finance assistant."},
        {"role": "user", "content": "Explain Black-Scholes delta vs gamma risk."}
    ],
    temperature=0.2,
    volatility_policy="financial_strict" # Auto-sets 300s TTL
)

print(f"Cached: {response.cache_hit} ({response.cache_tier})")
print(f"Latency Saved: {response.latency_saved_ms}ms")
print(f"Content: {response.choices[0].message.content}")`,
  },
  {
    language: "typescript",
    tabLabel: "TypeScript / Node",
    filename: "cachemind.ts",
    highlight: "Type-safe async client with automatic retries",
    code: `import { CacheMind } from "@cachemind/sdk";

const cachemind = new CacheMind({
  apiKey: process.env.CACHEMIND_API_KEY!,
  endpoint: "https://api.cachemind.ai/v1",
  similarityThreshold: 0.94,
});

async function runInference() {
  const result = await cachemind.chat.completions.create({
    model: "claude-3-5-sonnet",
    messages: [
      { role: "user", content: "Write a Rust generic binary heap with invariant tests." },
    ],
    metadata: { namespace: "engineering-docs", costCenter: "rnd-team-4" }
  });

  console.log(\`Cache State: \${result._cachemind?.status}\`); // "HIT_L2_SEMANTIC"
  console.log(\`Cosine Match: \${result._cachemind?.similarity}\`); // 0.984
  console.log(\`Tokens Saved: \${result.usage?.total_tokens}\`);
}

runInference();`,
  },
  {
    language: "python",
    tabLabel: "OpenAI 1-Line Drop-In",
    filename: "openai_dropin.py",
    highlight: "Zero-codebase changes — just point base_url to CacheMind",
    code: `from openai import OpenAI

# 1-Line Drop-in replacement! Point base_url to CacheMind Gateway
client = OpenAI(
    base_url="https://api.cachemind.ai/v1",
    api_key="cm_live_your_project_key_here"
)

# Standard OpenAI call — automatically accelerated by CacheMind L1/L2
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "How do distributed consensus algorithms work?"}],
    extra_headers={
        "X-CacheMind-Similarity-Threshold": "0.90",
        "X-CacheMind-Namespace": "knowledge-base"
    }
)

print(response.choices[0].message.content)`,
  },
  {
    language: "bash",
    tabLabel: "cURL CLI",
    filename: "request.sh",
    highlight: "Standard HTTP REST API for any programming language",
    code: `curl -X POST https://api.cachemind.ai/v1/chat/completions \\
  -H "Authorization: Bearer cm_live_your_project_key_here" \\
  -H "Content-Type: application/json" \\
  -H "X-CacheMind-Similarity-Threshold: 0.92" \\
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Calculate Q3 revenue growth and EBITDA."}
    ],
    "temperature": 0.0
  }'`,
  },
];

export default function CodeShowcase() {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [copied, setCopied] = useState<boolean>(false);

  const snippet = SNIPPETS[activeTab];

  const handleCopy = () => {
    navigator.clipboard.writeText(snippet.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="w-full bg-slate-950/80 border border-slate-800 shadow-2xl overflow-hidden backdrop-blur-xl">
      {/* Top tab bar */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-800 bg-slate-900/90 px-4 py-2 gap-2">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {SNIPPETS.map((s, idx) => (
            <button
              key={idx}
              onClick={() => {
                setActiveTab(idx);
                setCopied(false);
              }}
              className={`px-3 py-1.5 text-xs font-mono transition-all flex items-center gap-2 border ${
                activeTab === idx
                  ? "bg-slate-950 border-indigo-500 text-indigo-300 shadow-[0_0_10px_rgba(99,102,241,0.2)]"
                  : "bg-transparent border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              <Code className="w-3.5 h-3.5" />
              <span>{s.tabLabel}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono text-slate-400 hidden sm:inline">
            {snippet.filename}
          </span>
          <button
            onClick={handleCopy}
            className="text-xs font-mono px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">COPIED</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>COPY CODE</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Code viewer */}
      <div className="p-6 bg-slate-950/95 overflow-x-auto">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-800/80">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-[11px] font-mono text-indigo-300 font-semibold">
            {snippet.highlight}
          </span>
        </div>
        <pre className="text-xs font-mono text-slate-300 leading-relaxed">
          <code>{snippet.code}</code>
        </pre>
      </div>

      {/* Footer feature bar */}
      <div className="px-6 py-3 bg-slate-900/60 border-t border-slate-800 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 gap-3">
        <div className="flex items-center gap-2">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span>Zero changes to prompt logic or response handlers</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-emerald-400">✓ Streaming SSE Supported</span>
          <span className="text-indigo-400">✓ Multi-Tenant Headers</span>
        </div>
      </div>
    </div>
  );
}
