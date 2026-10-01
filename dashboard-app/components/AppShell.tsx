"use client";

import React, { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import {
  Cpu,
  LogOut,
  User as UserIcon,
  ShieldCheck,
  Building,
  KeyRound,
  ChevronDown,
  Menu,
  X,
} from "lucide-react";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { user, isAuthenticated, isLoading, activeWorkspace, workspaces, switchWorkspace, logout } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  const isPublicPage = pathname === "/" || pathname === "/login" || pathname === "/register" || pathname === "/signup";

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !isPublicPage) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, isPublicPage, router]);

  if (isPublicPage) {
    return <>{children}</>;
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#07090e] flex items-center justify-center font-mono text-xs text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span>INITIALIZING CONTROL PLANE SESSION...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
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
              <span className="text-slate-300">127.0.0.1:8000</span>
              <span className="text-emerald-400 font-bold">ARMED</span>
            </div>

            {/* Tenant Badge */}
            <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 bg-indigo-950/40 border border-indigo-800/50 text-[10px] font-mono text-indigo-300">
              <Building className="w-3 h-3 text-indigo-400" />
              <span>{activeWorkspace?.name || user?.organization || "Workspace"}</span>
            </div>

            {/* User Profile dropdown */}
            <div className="relative">
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="flex items-center gap-2 px-2.5 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-200 transition-all"
              >
                <UserIcon className="w-3.5 h-3.5 text-indigo-400" />
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
                      <div className="font-bold text-slate-100">{user?.name || "User"}</div>
                      <div className="text-[10px] text-slate-400 truncate">{user?.email}</div>
                      <div className="mt-1.5 flex items-center justify-between text-[10px]">
                        <span className="text-slate-500">ROLE:</span>
                        <span className="text-emerald-400 font-bold uppercase bg-emerald-950/80 border border-emerald-800 px-1.5 py-0.2">
                          {user?.role || "developer"}
                        </span>
                      </div>
                    </div>

                    {workspaces.length > 1 && (
                      <div className="py-1 border-b border-slate-800">
                        <div className="text-[9px] uppercase tracking-wider text-slate-500 font-bold mb-1">Switch Workspace</div>
                        {workspaces.map((ws) => (
                          <button
                            key={ws.id}
                            onClick={() => {
                              switchWorkspace(ws.id);
                              setUserDropdownOpen(false);
                            }}
                            className={`w-full text-left px-2 py-1 text-xs truncate flex items-center justify-between hover:bg-slate-900 ${
                              activeWorkspace?.id === ws.id ? "text-indigo-400 font-bold" : "text-slate-300"
                            }`}
                          >
                            <span className="truncate">{ws.name}</span>
                            {activeWorkspace?.id === ws.id && <span className="text-[9px]">ACTIVE</span>}
                          </button>
                        ))}
                      </div>
                    )}

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
