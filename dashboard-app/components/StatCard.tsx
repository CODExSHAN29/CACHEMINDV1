"use client";

import clsx from "clsx";
import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: string;
  trendPositive?: boolean;
  accent?: "emerald" | "cyan" | "amber" | "crimson" | "slate" | "blue";
  code?: string;
}

const ACCENT_STYLES = {
  blue: "text-primary bg-secondary-container border-blue-200",
  emerald: "text-emerald-700 bg-emerald-50 border-emerald-200",
  cyan: "text-blue-700 bg-blue-50 border-blue-200",
  amber: "text-amber-700 bg-amber-50 border-amber-200",
  crimson: "text-red-700 bg-red-50 border-red-200",
  slate: "text-on-surface-variant bg-surface-dim border-outline-variant",
};

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendPositive = true,
  accent = "blue",
  code,
}: StatCardProps) {
  return (
    <div className="card-shell p-5 relative group hover:border-on-surface-variant transition-colors">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="label-caps">{title}</span>
            {code && (
              <span className="text-[9px] font-mono text-on-surface-faint">
                [{code}]
              </span>
            )}
          </div>
          <div className="text-2xl font-mono font-bold text-on-surface tracking-tight tabular-nums">
            {value}
          </div>
        </div>

        {Icon && (
          <div
            className={clsx(
              "w-8 h-8 border flex items-center justify-center",
              ACCENT_STYLES[accent]
            )}
          >
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      {(subtitle || trend) && (
        <div className="mt-4 pt-3 border-t border-outline-variant flex items-center justify-between text-[11px] font-mono">
          {subtitle && <span className="text-on-surface-variant truncate">{subtitle}</span>}
          {trend && (
            <span
              className={clsx(
                "px-1.5 py-0.5 text-[10px] font-semibold border tabular-nums ml-auto",
                trendPositive
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-red-700 bg-red-50 border-red-200"
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
