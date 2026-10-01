"use client";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend } from "chart.js";
import { Line } from "react-chartjs-2";
import { TimeseriesPoint } from "@/lib/types";
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);
export default function RequestTimeseries({ points }: { points: TimeseriesPoint[] }) {
  const datasets = [{ label: "Exact hits", key: "exact_hits", color: "#10b981" }, { label: "Semantic hits", key: "semantic_hits", color: "#3b82f6" }, { label: "Misses", key: "misses", color: "#94a3b8" }].map(item => ({ label: item.label, data: points.map(p => p[item.key as "exact_hits"]), borderColor: item.color, borderWidth: 1, pointRadius: 0, tension: 0, fill: false }));
  return <div className="h-72 p-5"><Line data={{ labels: points.map(p => new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })), datasets }} options={{ responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { labels: { color: "#a0a9ba", boxWidth: 12, font: { size: 10 } } } }, scales: { x: { grid: { color: "#1a2030" }, ticks: { color: "#818b9e", maxTicksLimit: 8 } }, y: { beginAtZero: true, grid: { color: "#1a2030" }, ticks: { color: "#818b9e", precision: 0 } } } }} /></div>;
}
