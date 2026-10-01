"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard,
  Activity,
  Zap,
  KeyRound,
  CreditCard,
  Terminal,
  Cpu,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const navItems = [
  { name: "System Overview", href: "/dashboard", icon: LayoutDashboard, code: "01" },
  { name: "Telemetry & Savings", href: "/analytics", icon: Activity, code: "02" },
  { name: "Vector Cache Lifecycle", href: "/cache", icon: Zap, code: "03" },
  { name: "API Key Management", href: "/keys", icon: KeyRound, code: "04" },
  { name: "Metered Billing & Tiers", href: "/billing", icon: CreditCard, code: "05" },
  { name: "Inference Arena", href: "/playground", icon: Terminal, code: "06" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { activeWorkspace } = useAuth();

  return (
    <aside className="w-64 bg-[#07090e]/95 border-r border-slate-800/80 flex flex-col justify-between h-screen sticky top-0 select-none backdrop-blur-xl z-20">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center px-5 border-b border-slate-800/80 gap-3 bg-slate-950/60">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 bg-indigo-950/80 border border-indigo-500/50 flex items-center justify-center text-indigo-400 group-hover:border-indigo-400 group-hover:shadow-[0_0_15px_rgba(99,102,241,0.5)] transition-all">
              <Cpu className="w-4 h-4" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-display font-bold text-slate-100 text-sm tracking-tight uppercase">
                  CacheMind
                </span>
                <span className="text-[9px] font-mono px-1 py-0.2 bg-emerald-950/90 text-emerald-400 border border-emerald-800 font-semibold">
                  LIVE
                </span>
              </div>
              <span className="text-[9px] text-slate-500 font-mono tracking-wider">
                SEMANTIC GATEWAY v1.4
              </span>
            </div>
          </Link>
        </div>

        {/* Section Marker */}
        <div className="px-5 pt-5 pb-2">
          <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">
            // CONTROL MODULES
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="px-2 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex items-center justify-between px-3 py-2 text-xs font-mono transition-all duration-150 border",
                  isActive
                    ? "bg-slate-900 border-indigo-500/80 text-indigo-300 font-semibold shadow-[0_0_15px_rgba(99,102,241,0.15)]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50 border-transparent hover:border-slate-800"
                )}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={clsx(
                      "w-4 h-4 transition-colors",
                      isActive
                        ? "text-indigo-400"
                        : "text-slate-500 group-hover:text-slate-300"
                    )}
                  />
                  <span className="tracking-tight">{item.name}</span>
                </div>
                <span
                  className={clsx(
                    "text-[10px] tabular-nums font-mono",
                    isActive ? "text-indigo-400 font-bold" : "text-slate-600"
                  )}
                >
                  {item.code}
                </span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Industrial Telemetry Footer HUD */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/80">
        <div className="bg-slate-900/90 p-3 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">CLUSTER NODE</span>
            <span className="flex items-center gap-1.5 text-emerald-400 font-semibold text-[10px]">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
              ARMED // 200 OK
            </span>
          </div>

          <div className="border-t border-slate-800 pt-2 space-y-1 text-[10px] font-mono text-slate-400">
            <div className="flex justify-between">
              <span>L1/L2 ENGINE:</span>
              <span className="text-indigo-300 font-semibold">ONNX_BGE_384D</span>
            </div>
            <div className="flex justify-between">
              <span>TENANT SCOPE:</span>
              <span className="text-slate-200 font-semibold truncate max-w-[120px]" title={activeWorkspace?.name || activeWorkspace?.id || "default"}>
                {activeWorkspace?.name || activeWorkspace?.id || "N/A"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
