"use client";

import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Doughnut } from "react-chartjs-2";
import { PieChart } from "lucide-react";

ChartJS.register(ArcElement, Tooltip, Legend);

interface CacheRatioChartProps {
  exactHits: number;
  semanticHits: number;
  misses: number;
}

export default function CacheRatioChart({
  exactHits,
  semanticHits,
  misses,
}: CacheRatioChartProps) {
  const total = exactHits + semanticHits + misses;
  const hitPercentage = total > 0 ? Math.round(((exactHits + semanticHits) / total) * 100) : 0;

  const data = {
    labels: [
      "EXACT CACHE [L1]",
      "SEMANTIC CACHE [L2]",
      "UPSTREAM MISS",
    ],
    datasets: [
      {
        data: [exactHits || 1, semanticHits || 1, misses || 1],
        backgroundColor: ["#1d4ed8", "#2563eb", "#cbd5e1"],
        borderColor: "#ffffff",
        borderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "72%",
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: {
          color: "#475569",
          font: { family: "JetBrains Mono, monospace", size: 9 },
          boxWidth: 8,
          boxHeight: 8,
          usePointStyle: true,
          pointStyle: "rect",
          padding: 12,
        },
      },
      tooltip: {
        backgroundColor: "#ffffff",
        titleColor: "#0f172a",
        bodyColor: "#475569",
        borderColor: "#cbd5e1",
        borderWidth: 1,
        padding: 10,
        titleFont: { family: "JetBrains Mono, monospace", size: 11 },
        bodyFont: { family: "JetBrains Mono, monospace", size: 10 },
      },
    },
  };

  return (
    <div className="card-shell p-5 h-84 flex flex-col justify-between">
      <div className="flex items-center justify-between pb-3 border-b border-outline-variant mb-2">
        <div className="flex items-center gap-2">
          <PieChart className="w-4 h-4 text-primary" />
          <span className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
            CACHE DISTRIBUTION
          </span>
          <span className="text-[10px] font-mono text-on-surface-variant">[ZONE RATIO]</span>
        </div>
        <span className="badge-pill bg-blue-50 text-primary border-blue-200">
          {hitPercentage}% RETRIEVAL EFFICIENCY
        </span>
      </div>
      <div className="h-60 w-full relative flex items-center justify-center">
        <Doughnut data={data} options={options} />
      </div>
    </div>
  );
}
