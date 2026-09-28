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
        backgroundColor: ["#00F59B", "#00D2FF", "#222938"],
        borderColor: "#090B0F",
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
          color: "#94A3B8",
          font: { family: "JetBrains Mono, monospace", size: 9 },
          boxWidth: 8,
          boxHeight: 8,
          usePointStyle: true,
          pointStyle: "rect",
          padding: 12,
        },
      },
      tooltip: {
        backgroundColor: "#0C0E13",
        titleColor: "#FFFFFF",
        bodyColor: "#CBD5E1",
        borderColor: "#222938",
        borderWidth: 1,
        padding: 10,
        titleFont: { family: "JetBrains Mono, monospace", size: 11 },
        bodyFont: { family: "JetBrains Mono, monospace", size: 10 },
      },
    },
  };

  return (
    <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 h-84 flex flex-col justify-between">
      <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70 mb-2">
        <div className="flex items-center gap-2">
          <PieChart className="w-4 h-4 text-laser-cyan" />
          <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
            CACHE DISTRIBUTION
          </span>
          <span className="text-[10px] font-mono text-slate-400">[ZONE RATIO]</span>
        </div>
        <span className="text-[10px] text-laser-cyan font-mono bg-laser-cyan/10 border border-laser-cyan/30 px-2 py-0.5 rounded-sm font-semibold">
          {hitPercentage}% RETRIEVAL EFFICIENCY
        </span>
      </div>
      <div className="h-60 w-full relative flex items-center justify-center">
        <Doughnut data={data} options={options} />
      </div>
    </div>
  );
}
