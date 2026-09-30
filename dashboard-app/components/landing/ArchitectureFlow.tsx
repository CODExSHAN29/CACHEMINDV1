"use client";

import React, { useState } from "react";
import {
  Layers,
  Database,
  Cpu,
  ShieldCheck,
  Clock,
  ArrowRight,
  Sparkles,
  Server,
  Zap,
  CheckCircle,
} from "lucide-react";

interface PipelineStep {
  id: string;
  stepNumber: string;
  name: string;
  badge: string;
  latency: string;
  icon: any;
  color: string;
  description: string;
  techDetails: {
    engine: string;
    throughput: string;
    algorithm: string;
    guarantee: string;
  };
}

const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: "canonicalize",
    stepNumber: "01",
    name: "Canonicalization & Token Prep",
    badge: "INGRESS NORMALIZER",
    latency: "< 0.2ms",
    icon: Cpu,
    color: "indigo",
    description:
      "Normalizes whitespace, reorders JSON keys deterministically, strips system noise, and generates stable input fingerprints before hashing.",
    techDetails: {
      engine: "Rust/C-optimized Python Tokenizer",
      throughput: "140,000 req/sec",
      algorithm: "RFC-8785 JSON Canonicalization",
      guarantee: "100% Deterministic Fingerprints",
    },
  },
  {
    id: "l1_exact",
    stepNumber: "02",
    name: "L1 Clustered Redis Exact Cache",
    badge: "EXACT SHA-256 MATCH",
    latency: "< 0.4ms",
    icon: Zap,
    color: "cyan",
    description:
      "Performs atomic O(1) hash lookup on Clustered Redis. If prompt, model, and system parameters match exactly, returns instant cached response.",
    techDetails: {
      engine: "Redis Enterprise / Clustered In-Memory",
      throughput: "250,000 ops/sec",
      algorithm: "SHA-256 Cryptographic Hash Keying",
      guarantee: "Zero LLM compute on repeated queries",
    },
  },
  {
    id: "l2_semantic",
    stepNumber: "03",
    name: "L2 FastEmbed Semantic Vector Space",
    badge: "384D ONNX EMBEDDINGS",
    latency: "< 1.5ms",
    icon: Database,
    color: "purple",
    description:
      "Generates 384-dimensional dense semantic vectors using FastEmbed BGE-Small ONNX runtime and queries pgvector for high-cosine similarity matches (e.g. >0.92).",
    techDetails: {
      engine: "ONNX Runtime FastEmbed + pgvector / HNSW",
      throughput: "45,000 embeddings/sec (CPU-native)",
      algorithm: "BGE-Small-EN-v1.5 + Cosine Distance",
      guarantee: "Catches paraphrased and reworded queries",
    },
  },
  {
    id: "guardrails",
    stepNumber: "04",
    name: "Deterministic Guardrail Arbiter",
    badge: "SAFETY & INTEGRITY",
    latency: "< 0.3ms",
    icon: ShieldCheck,
    color: "emerald",
    description:
      "Verifies semantic validity, checks safety policies, validates JSON schema schemas, and rejects stale hallucinated content before response dispatch.",
    techDetails: {
      engine: "Rule-based Arbiter & Constraint Evaluator",
      throughput: "180,000 checks/sec",
      algorithm: "JSON Schema + Pydantic v2 + Regex Filter",
      guarantee: "No corrupt or out-of-schema payloads",
    },
  },
  {
    id: "volatility",
    stepNumber: "05",
    name: "Adaptive Volatility TTL Engine",
    badge: "INTELLIGENT EXPIRY",
    latency: "< 0.1ms",
    icon: Clock,
    color: "amber",
    description:
      "Classifies query freshness dynamically: static facts (30 days), docs (7 days), market data (60s), and real-time alerts (no-cache bypass).",
    techDetails: {
      engine: "Dynamic Volatility Engine",
      throughput: "300,000 evaluations/sec",
      algorithm: "Heuristic Entropy + Entity Timestamp Decay",
      guarantee: "Zero stale financial or time-sensitive data",
    },
  },
  {
    id: "fallback",
    stepNumber: "06",
    name: "Upstream LLM & Async Write-Behind",
    badge: "RESILIENT GATEWAY",
    latency: "P99 LLM Speed",
    icon: Server,
    color: "rose",
    description:
      "On cache miss, proxies seamlessly to OpenAI, Anthropic, or Ollama, streams response to client, and asynchronously writes embeddings in the background.",
    techDetails: {
      engine: "Asyncio Non-blocking Connection Pool",
      throughput: "Multi-provider Failover Support",
      algorithm: "Circuit Breaker + Exponential Backoff",
      guarantee: "100% Upstream Availability Fallback",
    },
  },
];

export default function ArchitectureFlow() {
  const [activeStep, setActiveStep] = useState<PipelineStep>(PIPELINE_STEPS[2]);

  return (
    <div className="w-full bg-slate-950/80 border border-slate-800 p-6 lg:p-10 shadow-2xl relative overflow-hidden">
      {/* Background Grid Pattern */}
      <div
        className="absolute inset-0 opacity-5 pointer-events-none"
        style={{
          backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.4) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />

      {/* Header */}
      <div className="max-w-3xl mb-10">
        <div className="flex items-center gap-2 mb-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          <span className="label-caps text-indigo-400">PRECISION ARCHITECTURE</span>
        </div>
        <h3 className="font-display font-bold text-3xl text-slate-100 tracking-tight">
          Multi-Tier Semantic Invalidation & Execution Pipeline
        </h3>
        <p className="text-xs font-mono text-slate-400 mt-2 leading-relaxed">
          Every incoming inference request passes through an enterprise 6-stage sub-millisecond pipeline
          combining cryptographic L1 keying, FastEmbed 384D ONNX vector semantic indexing, and deterministic guardrail validation.
        </p>
      </div>

      {/* Pipeline Navigation Steps */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 mb-8">
        {PIPELINE_STEPS.map((step) => {
          const isSelected = activeStep.id === step.id;
          const Icon = step.icon;

          return (
            <button
              key={step.id}
              onClick={() => setActiveStep(step)}
              className={`p-4 text-left transition-all relative border flex flex-col justify-between ${
                isSelected
                  ? "bg-slate-900 border-indigo-500 shadow-[0_0_20px_rgba(99,102,241,0.25)]"
                  : "bg-slate-950/70 border-slate-800/80 hover:bg-slate-900/60 hover:border-slate-700"
              }`}
            >
              {isSelected && (
                <div className="absolute top-0 left-0 right-0 h-0.5 bg-indigo-400 shadow-[0_0_8px_#818cf8]" />
              )}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-mono text-slate-500 font-bold">
                    STEP {step.stepNumber}
                  </span>
                  <span className="text-[10px] font-mono font-bold text-emerald-400">
                    {step.latency}
                  </span>
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className={`w-7 h-7 flex items-center justify-center border ${
                      isSelected
                        ? "bg-indigo-950 text-indigo-300 border-indigo-600"
                        : "bg-slate-900 text-slate-400 border-slate-800"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="text-xs font-mono font-bold text-slate-200 line-clamp-2">
                  {step.name}
                </div>
              </div>
              <div className="text-[9px] font-mono text-indigo-400 font-semibold uppercase mt-3 tracking-wider">
                {step.badge}
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected Step Deep Dive Inspector */}
      <div className="bg-slate-900/90 border border-indigo-500/40 p-6 lg:p-8 backdrop-blur-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-950/80 border border-indigo-500 flex items-center justify-center text-indigo-400">
              {React.createElement(activeStep.icon, { className: "w-5 h-5" })}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-indigo-400 uppercase">
                  PHASE {activeStep.stepNumber} // {activeStep.badge}
                </span>
              </div>
              <h4 className="font-display font-bold text-xl text-slate-100">
                {activeStep.name}
              </h4>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono bg-emerald-950/80 text-emerald-400 border border-emerald-800/80 px-2.5 py-1">
              PIPELINE LATENCY: {activeStep.latency}
            </span>
          </div>
        </div>

        <p className="text-xs font-mono text-slate-300 leading-relaxed max-w-4xl">
          {activeStep.description}
        </p>

        {/* Technical Specs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
          <div className="bg-slate-950 p-3.5 border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 mb-1 uppercase">Underlying Engine</div>
            <div className="text-xs font-mono font-bold text-indigo-300">
              {activeStep.techDetails.engine}
            </div>
          </div>

          <div className="bg-slate-950 p-3.5 border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 mb-1 uppercase">Benchmarked Throughput</div>
            <div className="text-xs font-mono font-bold text-emerald-400">
              {activeStep.techDetails.throughput}
            </div>
          </div>

          <div className="bg-slate-950 p-3.5 border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 mb-1 uppercase">Mathematical Algorithm</div>
            <div className="text-xs font-mono font-bold text-cyan-300">
              {activeStep.techDetails.algorithm}
            </div>
          </div>

          <div className="bg-slate-950 p-3.5 border border-slate-800">
            <div className="text-[10px] font-mono text-slate-400 mb-1 uppercase">Reliability Guarantee</div>
            <div className="text-xs font-mono font-bold text-slate-200">
              {activeStep.techDetails.guarantee}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
