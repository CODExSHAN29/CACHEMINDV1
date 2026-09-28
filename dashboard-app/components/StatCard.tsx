"use client";

import clsx from "clsx";
import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon | React.ComponentType<{ className?: string }> | React.ReactNode;
  trend?: string;
  trendPositive?: boolean;
  accent?: "emerald" | "cyan" | "amber" | "crimson" | "slate";
  code?: string;
}

export default function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendPositive = true,
  accent = "emerald",
  code,
}: StatCardProps) {
  const accentColors = {
    emerald: "text-laser-emerald border-laser-emerald/30 bg-laser-emerald/5",
    cyan: "text-laser-cyan border-laser-cyan/30 bg-laser-cyan/5",
    amber: "text-laser-amber border-laser-amber/30 bg-laser-amber/5",
    crimson: "text-laser-crimson border-laser-crimson/30 bg-laser-crimson/5",
    slate: "text-slate-300 border-slate-700 bg-carbon-800",
  };

  const renderIcon = () => {
    if (!icon) return null;
    if (React.isValidElement(icon)) return icon;
    // Icon is a component (Lucide icon or React component)
    const IconComponent = icon as React.ComponentType<{ className?: string }>;
    return <IconComponent className="w-4 h-4" />;
  };

  return (
    <div className="industrial-panel rounded-sm p-5 bg-carbon-900 border border-carbon-750/90 relative group hover:border-carbon-600 transition-colors">
      {/* Header bar */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400 font-semibold">
              {title}
            </span>
            {code && (
              <span className="text-[9px] font-mono text-slate-400">
                [{code}]
              </span>
            )}
          </div>
          <div className="text-2xl font-mono font-bold text-white tracking-tight tabular-nums">
            {value}
          </div>
        </div>

        {/* Vector Icon */}
        <div
          className={clsx(
            "w-9 h-9 rounded-sm border flex items-center justify-center transition-transform group-hover:scale-105",
            accentColors[accent]
          )}
        >
          {renderIcon()}
        </div>
      </div>

      {/* Subtitle & Trend HUD */}
      {(subtitle || trend) && (
        <div className="mt-4 pt-3 border-t border-carbon-750/60 flex items-center justify-between text-[11px] font-mono">
          {subtitle && <span className="text-slate-400 truncate">{subtitle}</span>}
          {trend && (
            <span
              className={clsx(
                "px-1.5 py-0.5 rounded-sm text-[10px] font-semibold border tabular-nums ml-auto",
                trendPositive
                  ? "text-laser-emerald bg-laser-emerald/10 border-laser-emerald/30"
                  : "text-laser-crimson bg-laser-crimson/10 border-laser-crimson/30"
              )}
            >
              {trend}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
