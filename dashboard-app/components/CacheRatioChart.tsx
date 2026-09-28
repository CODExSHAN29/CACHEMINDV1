"use client";

import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Doughnut } from "react-chartjs-2";

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
    labels: ["Exact Cache (L1)", "Semantic Cache (L2)", "Provider Misses"],
    datasets: [
      {
        data: [exactHits || 1, semanticHits || 1, misses || 1],
        backgroundColor: ["#3b82f6", "#a855f7", "#374151"],
        borderColor: "#111827",
        borderWidth: 3,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "70%",
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: {
          color: "#9ca3af",
          font: { size: 11 },
          boxWidth: 10,
          padding: 12,
        },
      },
      tooltip: {
        backgroundColor: "#111827",
        titleColor: "#fff",
        bodyColor: "#9ca3af",
        borderColor: "#374151",
        borderWidth: 1,
      },
    },
  };

  return (
    <div className="bg-dark-card border border-dark-border rounded-xl p-5 h-80 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-white">Cache Hit Breakdown</h4>
        <span className="text-xs text-blue-400 font-mono bg-blue-950/60 border border-blue-800/40 px-2 py-0.5 rounded">
          {hitPercentage}% Efficiency
        </span>
      </div>
      <div className="h-60 w-full relative flex items-center justify-center">
        <Doughnut data={data} options={options} />
      </div>
    </div>
  );
}
