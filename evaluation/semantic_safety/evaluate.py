#!/usr/bin/env python3
"""
CacheMind Semantic Safety & Guardrail Evaluator.

Scientifically compares:
1. Baseline Raw Cosine Similarity (Semantic Vector Search alone)
2. CacheMind Guardrail Arbiter Enhanced Matching (Cosine Similarity + Deterministic Safety Pillars)

Measures False Positive Rate (Semantic Cache Poisoning), Precision, Recall, F1,
and per-category vulnerability across 600+ benchmark prompt pairs.
"""

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.guardrails.arbiter import GuardrailArbiter, GuardrailDecision
from backend.semantic.embedding import EmbeddingEngine

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "results"


@dataclass
class ConfusionMatrix:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def precision(self) -> float:
        return (self.tp / (self.tp + self.fp)) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return (self.tp / (self.tp + self.fn)) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        return ((self.tp + self.tn) / self.total) if self.total > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        """FPR = FP / (FP + TN) — Measure of Semantic Cache Poisoning rate."""
        return (self.fp / (self.fp + self.tn)) if (self.fp + self.tn) > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
        }


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def run_evaluation(
    dataset: List[Dict[str, Any]],
    threshold: float = 0.90,
    embedding_engine: Optional[EmbeddingEngine] = None,
) -> Dict[str, Any]:
    """Evaluates dataset under raw cosine similarity vs Guardrail Arbiter."""
    if embedding_engine is None:
        embedding_engine = EmbeddingEngine()
        embedding_engine._warmup()

    arbiter = GuardrailArbiter()

    # Pre-extract all unique texts to batch embed
    unique_texts = list(set([item["prompt_a"] for item in dataset] + [item["prompt_b"] for item in dataset]))
    print(f"[*] Embedding {len(unique_texts)} unique query prompts via FastEmbed...")
    embeddings_list = embedding_engine._embed_batch_sync(unique_texts)
    text_to_vec = {t: v for t, v in zip(unique_texts, embeddings_list)}

    raw_overall = ConfusionMatrix()
    arbiter_overall = ConfusionMatrix()

    categories = list(set(item["category"] for item in dataset))
    raw_by_category: Dict[str, ConfusionMatrix] = {c: ConfusionMatrix() for c in categories}
    arbiter_by_category: Dict[str, ConfusionMatrix] = {c: ConfusionMatrix() for c in categories}

    pair_evaluations: List[Dict[str, Any]] = []

    for item in dataset:
        p_a = item["prompt_a"]
        p_b = item["prompt_b"]
        expected = item["expected_match"]
        cat = item["category"]

        vec_a = text_to_vec[p_a]
        vec_b = text_to_vec[p_b]
        sim = compute_cosine_similarity(vec_a, vec_b)

        # Baseline: Raw Cosine Similarity
        raw_pred = sim >= threshold

        # CacheMind: Cosine Similarity + Guardrail Arbiter
        decision: GuardrailDecision = asyncio.run(
            arbiter.evaluate(
                incoming_text=p_a,
                candidate_text=p_b,
                incoming_system_prompt=None,
                candidate_system_prompt=None,
            )
        )
        arbiter_pred = (sim >= threshold) and decision.passed

        # Update Raw CM
        if raw_pred and expected:
            raw_overall.tp += 1
            raw_by_category[cat].tp += 1
        elif raw_pred and not expected:
            raw_overall.fp += 1
            raw_by_category[cat].fp += 1
        elif not raw_pred and not expected:
            raw_overall.tn += 1
            raw_by_category[cat].tn += 1
        else:
            raw_overall.fn += 1
            raw_by_category[cat].fn += 1

        # Update Arbiter CM
        if arbiter_pred and expected:
            arbiter_overall.tp += 1
            arbiter_by_category[cat].tp += 1
        elif arbiter_pred and not expected:
            arbiter_overall.fp += 1
            arbiter_by_category[cat].fp += 1
        elif not arbiter_pred and not expected:
            arbiter_overall.tn += 1
            arbiter_by_category[cat].tn += 1
        else:
            arbiter_overall.fn += 1
            arbiter_by_category[cat].fn += 1

        pair_evaluations.append({
            "id": item["id"],
            "category": cat,
            "similarity": round(sim, 4),
            "expected_match": expected,
            "raw_pred": raw_pred,
            "arbiter_decision": {
                "passed": decision.passed,
                "reason": decision.reason,
                "failed_checks": decision.failed_checks,
            },
            "arbiter_pred": arbiter_pred,
            "prompt_a": p_a,
            "prompt_b": p_b,
        })

    return {
        "threshold": threshold,
        "sample_count": len(dataset),
        "raw_cosine": {
            "overall": raw_overall.to_dict(),
            "by_category": {c: cm.to_dict() for c, cm in raw_by_category.items()},
        },
        "guardrail_arbiter": {
            "overall": arbiter_overall.to_dict(),
            "by_category": {c: cm.to_dict() for c, cm in arbiter_by_category.items()},
        },
        "evaluations": pair_evaluations,
    }


def run_threshold_sweep(
    dataset: List[Dict[str, Any]],
    start: float = 0.85,
    stop: float = 0.98,
    step: float = 0.01,
) -> Dict[str, Any]:
    """Runs a sweep of similarity thresholds and returns precision/recall/FPR curves."""
    embedding_engine = EmbeddingEngine()
    embedding_engine._warmup()

    thresholds = [round(t, 3) for t in np.arange(start, stop + (step / 2.0), step)]
    sweep_results = []

    print(f"\n[*] Running Threshold Sweep ({start:.2f} to {stop:.2f} in steps of {step:.2f})...")
    for t in thresholds:
        res = run_evaluation(dataset=dataset, threshold=t, embedding_engine=embedding_engine)
        sweep_results.append({
            "threshold": t,
            "raw_cosine": res["raw_cosine"]["overall"],
            "guardrail_arbiter": res["guardrail_arbiter"]["overall"],
            "raw_fpr_by_category": {
                cat: metrics["false_positive_rate"]
                for cat, metrics in res["raw_cosine"]["by_category"].items()
            },
            "arbiter_fpr_by_category": {
                cat: metrics["false_positive_rate"]
                for cat, metrics in res["guardrail_arbiter"]["by_category"].items()
            },
        })

    return {
        "metadata": {
            "start_threshold": start,
            "stop_threshold": stop,
            "step": step,
            "total_eval_pairs": len(dataset),
            "timestamp": time.time(),
        },
        "sweep": sweep_results,
    }


def print_evaluation_report(results: Dict[str, Any]) -> None:
    t = results["threshold"]
    raw = results["raw_cosine"]["overall"]
    arb = results["guardrail_arbiter"]["overall"]

    print("\n" + "=" * 90)
    print(f" [!] CACHEMIND SEMANTIC SAFETY EVALUATION (Threshold tau = {t:.2f})")
    print("=" * 90)
    print(f"{'Metric':<28} | {'Raw Cosine Alone':>18} | {'CacheMind Guardrails':>22} | {'Delta':>12}")
    print("-" * 90)

    rows = [
        ("Precision", raw["precision"] * 100, arb["precision"] * 100, "%"),
        ("Recall", raw["recall"] * 100, arb["recall"] * 100, "%"),
        ("F1-Score", raw["f1_score"] * 100, arb["f1_score"] * 100, "%"),
        ("Overall Accuracy", raw["accuracy"] * 100, arb["accuracy"] * 100, "%"),
        ("False Positive Rate (FPR)", raw["false_positive_rate"] * 100, arb["false_positive_rate"] * 100, "%"),
        ("Total False Positives (FP)", raw["fp"], arb["fp"], " cases"),
        ("True Negatives (TN)", raw["tn"], arb["tn"], " cases"),
        ("True Positives (TP)", raw["tp"], arb["tp"], " cases"),
    ]

    for label, val_raw, val_arb, unit in rows:
        delta = val_arb - val_raw
        if unit == "%":
            sign = "+" if delta >= 0 else ""
            print(f"{label:<28} | {val_raw:17.2f}% | {val_arb:21.2f}% | {sign}{delta:10.2f}%")
        else:
            sign = "+" if delta >= 0 else ""
            print(f"{label:<28} | {val_raw:14d}{unit} | {val_arb:18d}{unit} | {sign}{delta:8d}")

    print("=" * 90)
    print(" [*] VULNERABILITY BREAKDOWN BY CRITICAL FAILURE CATEGORY (False Positive Rate %):")
    print(f"{'Category':<24} | {'Raw Cosine FPR':>16} | {'Guardrail Arbiter FPR':>22} | {'Safety Defense':>15}")
    print("-" * 90)

    for cat in results["raw_cosine"]["by_category"].keys():
        raw_fpr = results["raw_cosine"]["by_category"][cat]["false_positive_rate"] * 100.0
        arb_fpr = results["guardrail_arbiter"]["by_category"][cat]["false_positive_rate"] * 100.0
        defense = "PASS (100% Safe)" if arb_fpr == 0.0 else f"Poison Risk ({arb_fpr:.1f}%)"
        print(f"{cat:<24} | {raw_fpr:15.1f}% | {arb_fpr:21.1f}% | {defense:>15}")

    print("=" * 90 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheMind Semantic Safety Evaluator")
    parser.add_argument("--dataset", default=str(DATASET_PATH), help="Path to dataset.jsonl")
    parser.add_argument("--threshold", type=float, default=0.90, help="Similarity threshold")
    parser.add_argument("--sweep", action="store_true", help="Run full threshold sweep 0.85-0.98")
    parser.add_argument("--sweep-start", type=float, default=0.85, help="Sweep start")
    parser.add_argument("--sweep-stop", type=float, default=0.98, help="Sweep stop")
    parser.add_argument("--sweep-step", type=float, default=0.01, help="Sweep step")
    parser.add_argument("--output", default=None, help="Output JSON results path")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[-] Dataset file not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    dataset = load_dataset(dataset_path)

    if args.sweep:
        sweep_data = run_threshold_sweep(
            dataset=dataset,
            start=args.sweep_start,
            stop=args.sweep_stop,
            step=args.sweep_step,
        )
        out_path = (
            Path(args.output)
            if args.output
            else DEFAULT_OUTPUT_DIR / f"threshold_sweep_{int(time.time())}.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sweep_data, f, indent=2)
        print(f"[+] Saved threshold sweep results to: {out_path}")

        # Also write canonical threshold_sweep.json
        canonical_sweep = Path(__file__).resolve().parent / "threshold_sweep.json"
        with open(canonical_sweep, "w", encoding="utf-8") as f:
            json.dump(sweep_data, f, indent=2)
        print(f"[+] Updated canonical sweep at: {canonical_sweep}")
    else:
        results = run_evaluation(dataset=dataset, threshold=args.threshold)
        print_evaluation_report(results)

        out_path = (
            Path(args.output)
            if args.output
            else DEFAULT_OUTPUT_DIR / f"eval_t{args.threshold}_{int(time.time())}.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"[+] Saved evaluation report to: {out_path}")


if __name__ == "__main__":
    main()
