"use client";

import clsx from "clsx";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: string;
  trend?: string;
  trendPositive?: boolean;
  highlight?: boolean;
}

export default function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendPositive,
  highlight,
}: StatCardProps) {
  return (
    <div
      className={clsx(
        "rounded-xl p-5 border transition-all duration-200 relative overflow-hidden",
        highlight
          ? "bg-gradient-to-b from-blue-950/30 to-dark-card border-blue-500/30 shadow-lg shadow-blue-500/5"
          : "bg-dark-card border-dark-border hover:border-gray-700"
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{title}</p>
          <h3 className="text-2xl font-bold text-white mt-1.5 tracking-tight">{value}</h3>
        </div>
        <div className="w-10 h-10 rounded-lg bg-dark-bg/80 border border-dark-border/80 flex items-center justify-center text-lg">
          {icon}
        </div>
      </div>

      {(subtitle || trend) && (
        <div className="mt-3.5 flex items-center gap-2 text-xs">
          {trend && (
            <span
              className={clsx(
                "font-semibold px-1.5 py-0.5 rounded text-[11px]",
                trendPositive
                  ? "text-emerald-400 bg-emerald-950/60 border border-emerald-800/40"
                  : "text-rose-400 bg-rose-950/60 border border-rose-800/40"
              )}
            >
              {trend}
            </span>
          )}
          {subtitle && <span className="text-gray-400">{subtitle}</span>}
        </div>
      )}
    </div>
  );
}
