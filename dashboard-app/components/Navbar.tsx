"use client";

import { useState, useEffect } from "react";
import { Toaster } from "react-hot-toast";
import { Clock, Cpu, User, LogOut, ChevronDown } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function Navbar() {
  const { user, activeWorkspace, workspaces, switchWorkspace, logout } = useAuth();
  const [time, setTime] = useState<string>("");
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTime(now.toISOString().replace("T", " ").substring(0, 19) + " UTC");
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#ffffff",
            color: "#0f172a",
            border: "1px solid #cbd5e1",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            borderRadius: "0px",
          },
        }}
      />
      <header className="h-14 border-b border-outline bg-surface sticky top-0 z-30 flex items-center justify-between px-6">
        {/* Left Telemetry Indicators */}
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-emerald-600 animate-pulse"></span>
            <span className="label-caps">GATEWAY:</span>
            <span className="text-[11px] font-mono text-on-surface bg-surface-dim px-2 py-0.5 border border-outline-variant">
              ONLINE // 127.0.0.1:8000
            </span>
          </div>

          <div className="hidden lg:flex items-center gap-2">
            <span className="label-caps">EMBEDDER:</span>
            <span className="text-[11px] font-mono text-primary bg-secondary-container px-2 py-0.5 border border-blue-200">
              FASTEMBED // BGE-SMALL-EN-V1.5 (384D)
            </span>
          </div>
        </div>

        {/* Right Controls & User Info */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-on-surface-variant bg-surface-dim px-2.5 py-1 border border-outline-variant">
            <Clock className="w-3.5 h-3.5 text-on-surface-variant" />
            <span className="tabular-nums">{time || "2026-10-01 00:00:00 UTC"}</span>
          </div>

          {user && (
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 text-xs font-mono font-semibold bg-surface hover:bg-surface-dim text-on-surface px-3 py-1.5 border border-outline transition-colors"
              >
                <User className="w-3.5 h-3.5 text-primary" />
                <span className="max-w-[150px] truncate">{user.email}</span>
                <ChevronDown className="w-3 h-3 text-slate-400" />
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-1 w-64 bg-surface border border-outline shadow-lg z-50 p-2 font-mono text-xs">
                  <div className="px-2 py-1.5 border-b border-outline-variant">
                    <p className="font-bold text-on-surface truncate">{user.name}</p>
                    <p className="text-[10px] text-on-surface-variant truncate">{user.email}</p>
                  </div>

                  {workspaces.length > 1 && (
                    <div className="py-1.5 border-b border-outline-variant">
                      <p className="px-2 text-[9px] uppercase tracking-wider text-slate-400 font-bold mb-1">Switch Workspace</p>
                      {workspaces.map((ws) => (
                        <button
                          key={ws.id}
                          onClick={() => {
                            switchWorkspace(ws.id);
                            setShowUserMenu(false);
                          }}
                          className={`w-full text-left px-2 py-1 text-xs truncate flex items-center justify-between hover:bg-surface-dim ${
                            activeWorkspace?.id === ws.id ? "text-primary font-bold" : "text-on-surface"
                          }`}
                        >
                          <span className="truncate">{ws.name}</span>
                          {activeWorkspace?.id === ws.id && <span className="text-[10px]">ACTIVE</span>}
                        </button>
                      ))}
                    </div>
                  )}

                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      logout();
                    }}
                    className="w-full text-left px-2 py-1.5 text-rose-600 hover:bg-rose-50 flex items-center gap-2 mt-1"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </header>
    </>
  );
}
