"use client";

import React, { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import {
  Cpu,
  Sparkles,
  LogOut,
  User as UserIcon,
  ShieldCheck,
  Building,
  KeyRound,
  ExternalLink,
  ChevronDown,
  Menu,
  X,
  Zap,
} from "lucide-react";

function GithubIconSmall({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
      />
    </svg>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { user, isAuthenticated, logout, tenantId, planTier } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  const isPublicPage = pathname === "/" || pathname === "/login" || pathname === "/register";

  if (isPublicPage) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-[#07090e] text-[#f1f5f9] flex overflow-x-hidden selection:bg-indigo-500/30 selection:text-indigo-100">
      {/* Desktop Sidebar */}
      <div className="hidden md:block shrink-0">
        <Sidebar />
      </div>

      {/* Mobile Drawer */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="relative z-10 w-72 max-w-[85vw] h-full bg-[#07090e] border-r border-slate-800">
            <div className="p-4 flex items-center justify-between border-b border-slate-800">
              <span className="font-display font-bold text-sm tracking-tight">CACHEMIND CONSOLE</span>
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="p-1 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <Sidebar />
          </div>
        </div>
      )}

      {/* Main Console Workspace */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Global Console Top Nav */}
        <header className="h-14 bg-[#090d16]/95 border-b border-slate-800/80 sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 backdrop-blur-xl">
          {/* Left: Mobile trigger & Breadcrumbs */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="md:hidden p-1.5 text-slate-400 hover:text-white border border-slate-800 bg-slate-900/60"
            >
              <Menu className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2 font-mono text-xs text-slate-400">
              <span className="text-slate-500 uppercase tracking-wider">// CONSOLE</span>
              <span className="text-slate-600">/</span>
              <span className="text-indigo-400 font-semibold uppercase tracking-wider">
                {pathname.replace("/", "") || "DASHBOARD"}
              </span>
            </div>
          </div>

          {/* Right: Tenant, Gateway Status & User Profile */}
          <div className="flex items-center gap-3 sm:gap-4">
            {/* Gateway status indicator */}
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 bg-slate-900/80 border border-slate-800 text-[10px] font-mono">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span className="text-slate-300">0.0.0.0:8000</span>
              <span className="text-emerald-400 font-bold">ARMED</span>
            </div>

            {/* Tenant Badge */}
            <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 bg-indigo-950/40 border border-indigo-800/50 text-[10px] font-mono text-indigo-300">
              <Building className="w-3 h-3 text-indigo-400" />
              <span>{user?.organization || tenantId}</span>
            </div>

            {/* User Profile dropdown */}
            <div className="relative">
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="flex items-center gap-2 px-2.5 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-200 transition-all"
              >
                {user?.provider === "github" ? (
                  <GithubIconSmall className="text-slate-300" />
                ) : (
                  <UserIcon className="w-3.5 h-3.5 text-indigo-400" />
                )}
                <span className="font-semibold">{user?.name || "Developer"}</span>
                <ChevronDown className="w-3 h-3 text-slate-500" />
              </button>

              {userDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setUserDropdownOpen(false)}
                  />
                  <div className="absolute right-0 mt-2 w-64 bg-slate-950 border border-slate-800 shadow-2xl p-3 z-50 font-mono text-xs space-y-3">
                    <div className="pb-2 border-b border-slate-800">
                      <div className="font-bold text-slate-100">{user?.name || "Active Developer"}</div>
                      <div className="text-[10px] text-slate-400 truncate">{user?.email || "developer@cachemind.ai"}</div>
                      <div className="mt-1.5 flex items-center justify-between text-[10px]">
                        <span className="text-slate-500">TIER:</span>
                        <span className="text-emerald-400 font-bold uppercase bg-emerald-950/80 border border-emerald-800 px-1.5 py-0.2">
                          {planTier}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <Link
                        href="/keys"
                        onClick={() => setUserDropdownOpen(false)}
                        className="flex items-center justify-between px-2 py-1.5 hover:bg-slate-900 text-slate-300 hover:text-white"
                      >
                        <span className="flex items-center gap-2">
                          <KeyRound className="w-3.5 h-3.5 text-indigo-400" /> API Keys
                        </span>
                      </Link>
                      <Link
                        href="/billing"
                        onClick={() => setUserDropdownOpen(false)}
                        className="flex items-center justify-between px-2 py-1.5 hover:bg-slate-900 text-slate-300 hover:text-white"
                      >
                        <span className="flex items-center gap-2">
                          <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" /> Subscription
                        </span>
                      </Link>
                    </div>

                    <div className="pt-2 border-t border-slate-800">
                      <button
                        onClick={() => {
                          setUserDropdownOpen(false);
                          logout();
                        }}
                        className="w-full flex items-center justify-center gap-2 py-1.5 bg-rose-950/40 hover:bg-rose-900/60 border border-rose-900/60 text-rose-300 font-bold text-xs transition-colors"
                      >
                        <LogOut className="w-3.5 h-3.5" /> SIGN OUT
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        {/* Workspace Route View */}
        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
