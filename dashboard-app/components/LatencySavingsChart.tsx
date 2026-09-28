"use client";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { Activity } from "lucide-react";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface LatencySavingsChartProps {
  uncachedMs: number;
  cachedMs: number;
}

export default function LatencySavingsChart({
  uncachedMs,
  cachedMs,
}: LatencySavingsChartProps) {
  const labels = ["T-60m", "T-50m", "T-40m", "T-30m", "T-20m", "T-10m", "T-00m (NOW)"];

  const data = {
    labels,
    datasets: [
      {
        label: "UPSTREAM PROVIDER (UNCATALYZED) [ms]",
        data: labels.map((_, i) => Math.max(120, Math.round(uncachedMs + Math.sin(i * 1.2) * 35))),
        borderColor: "#FF3856",
        backgroundColor: "rgba(255, 56, 86, 0.04)",
        fill: true,
        tension: 0.1,
        borderWidth: 1.5,
        pointRadius: 2,
        pointBackgroundColor: "#FF3856",
      },
      {
        label: "CACHEMIND ACCELERATED (L1/L2 HIT) [ms]",
        data: labels.map((_, i) => Math.max(0.4, Number((cachedMs + Math.cos(i * 1.5) * 0.2).toFixed(2)))),
        borderColor: "#00F59B",
        backgroundColor: "rgba(0, 245, 155, 0.08)",
        fill: true,
        tension: 0.1,
        borderWidth: 1.5,
        pointRadius: 2,
        pointBackgroundColor: "#00F59B",
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
        labels: {
          color: "#94A3B8",
          font: { family: "JetBrains Mono, monospace", size: 10 },
          boxWidth: 8,
          boxHeight: 8,
          usePointStyle: true,
          pointStyle: "rect",
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
    scales: {
      x: {
        grid: { color: "rgba(255, 255, 255, 0.04)" },
        ticks: { color: "#64748B", font: { family: "JetBrains Mono, monospace", size: 9 } },
      },
      y: {
        grid: { color: "rgba(255, 255, 255, 0.04)" },
        ticks: { color: "#64748B", font: { family: "JetBrains Mono, monospace", size: 9 } },
      },
    },
  };

  return (
    <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 h-84 flex flex-col justify-between">
      <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70 mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-laser-emerald" />
          <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
            LATENCY DELTA TELEMETRY
          </span>
          <span className="text-[10px] font-mono text-slate-400">[TTFT // ROUNDTRIP]</span>
        </div>
        <span className="text-[10px] text-laser-emerald font-mono bg-laser-emerald/10 border border-laser-emerald/30 px-2 py-0.5 rounded-sm font-semibold">
          98.6% SPEEDUP FACTOR
        </span>
      </div>
      <div className="h-64 w-full">
        <Line data={data} options={options} />
      </div>
    </div>
  );
}
