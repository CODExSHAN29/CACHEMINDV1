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
  ShieldCheck,
  CircleDot,
} from "lucide-react";

const navItems = [
  { name: "System Overview", href: "/", icon: LayoutDashboard, code: "01" },
  { name: "Telemetry & Savings", href: "/analytics", icon: Activity, code: "02" },
  { name: "Cache Engine Lifecycle", href: "/cache", icon: Zap, code: "03" },
  { name: "API Key Management", href: "/keys", icon: KeyRound, code: "04" },
  { name: "Metered Billing & Tiers", href: "/billing", icon: CreditCard, code: "05" },
  { name: "Inference Playground", href: "/playground", icon: Terminal, code: "06" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-carbon-900 border-r border-carbon-750/80 flex flex-col justify-between h-screen sticky top-0 select-none">
      <div>
        {/* Technical Brand Header */}
        <div className="h-16 flex items-center px-5 border-b border-carbon-750/80 gap-3 bg-carbon-950/60">
          <div className="w-8 h-8 rounded-sm bg-carbon-800 border border-carbon-700 flex items-center justify-center text-laser-emerald shadow-inner">
            <Cpu className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="font-mono font-bold text-white text-sm tracking-wider uppercase">
                CacheMind
              </span>
              <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-laser-emerald/10 text-laser-emerald border border-laser-emerald/20 font-semibold">
                PROD
              </span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono tracking-tight">
              GATEWAY // CONTROL PLANE
            </span>
          </div>
        </div>

        {/* Section Marker */}
        <div className="px-5 pt-5 pb-2">
          <span className="text-[10px] font-mono font-semibold tracking-widest text-slate-400 uppercase">
            CONTROL MODULES
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="px-3 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex items-center justify-between px-3 py-2 rounded-sm text-xs font-mono transition-all duration-150 group",
                  isActive
                    ? "bg-carbon-800 text-white border-l-2 border-laser-emerald shadow-sm"
                    : "text-slate-400 hover:text-slate-100 hover:bg-carbon-850"
                )}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={clsx(
                      "w-4 h-4 transition-colors",
                      isActive
                        ? "text-laser-emerald"
                        : "text-slate-400 group-hover:text-slate-200"
                    )}
                  />
                  <span className="tracking-wide">{item.name}</span>
                </div>
                <span
                  className={clsx(
                    "text-[10px] tabular-nums font-mono",
                    isActive ? "text-laser-emerald/70" : "text-slate-400"
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
      <div className="p-3 border-t border-carbon-750/80 bg-carbon-950/40">
        <div className="bg-carbon-950 rounded-sm p-3 border border-carbon-750 space-y-2">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-slate-400">CLUSTER NODE</span>
            <span className="flex items-center gap-1.5 text-laser-emerald font-semibold text-[10px]">
              <span className="w-1.5 h-1.5 rounded-full bg-laser-emerald status-led"></span>
              ARMED // 200 OK
            </span>
          </div>

          <div className="border-t border-carbon-750/60 pt-2 space-y-1 text-[10px] font-mono text-slate-400">
            <div className="flex justify-between">
              <span>L1 / L2 CACHE:</span>
              <span className="text-slate-300">FASTEMBED_ONNX</span>
            </div>
            <div className="flex justify-between">
              <span>TENANT ID:</span>
              <span className="text-slate-300">tenant_default</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
