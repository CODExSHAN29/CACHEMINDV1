"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const navItems = [
  { name: "Overview", href: "/", icon: "📊" },
  { name: "Analytics & Savings", href: "/analytics", icon: "📈" },
  { name: "Cache Engine", href: "/cache", icon: "⚡" },
  { name: "API Keys & Access", href: "/keys", icon: "🔑" },
  { name: "Billing & Plans", href: "/billing", icon: "💳" },
  { name: "Interactive Playground", href: "/playground", icon: "🧪" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-dark-card border-r border-dark-border flex flex-col justify-between h-screen sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-dark-border gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-purple-600 flex items-center justify-center font-bold text-lg shadow-lg shadow-blue-500/20">
            ⚡
          </div>
          <div>
            <h1 className="font-bold text-white text-base tracking-wide">CacheMind</h1>
            <p className="text-xs text-gray-400 font-mono">Gateway v0.1.0</p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-4 space-y-1.5">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-blue-600/15 text-blue-400 border border-blue-500/30 shadow-sm shadow-blue-500/10"
                    : "text-gray-400 hover:text-white hover:bg-dark-hover"
                )}
              >
                <span className="text-base">{item.icon}</span>
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer / Status */}
      <div className="p-4 border-t border-dark-border">
        <div className="bg-dark-bg/60 rounded-lg p-3 border border-dark-border/60">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
            <span>Cluster Status</span>
            <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Operational
            </span>
          </div>
          <div className="text-[11px] text-gray-500 font-mono truncate">
            Tenant: tenant_default
          </div>
        </div>
      </div>
    </aside>
  );
}
