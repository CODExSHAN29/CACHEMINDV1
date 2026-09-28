"use client";

import { useState, useEffect } from "react";
import toast, { Toaster } from "react-hot-toast";
import { KeyRound, ShieldCheck, Cpu, X, Check, Clock, Radio } from "lucide-react";

export default function Navbar() {
  const [apiKey, setApiKey] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    setApiKey(localStorage.getItem("cachemind_api_key") || "cm_live_development_test_key_000000000000000000000000");
    setAdminKey(localStorage.getItem("cachemind_admin_key") || "cm_admin_master_secret_key_9999999999999999");

    const updateClock = () => {
      const now = new Date();
      setTime(now.toISOString().replace("T", " ").substring(0, 19) + " UTC");
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleSaveKeys = () => {
    localStorage.setItem("cachemind_api_key", apiKey.trim());
    localStorage.setItem("cachemind_admin_key", adminKey.trim());
    toast.success("Gateway authentication credentials securely cached.");
    setIsOpen(false);
  };

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#0E1117",
            color: "#F3F4F6",
            border: "1px solid #222938",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
          },
        }}
      />
      <header className="h-16 border-b border-carbon-750/80 bg-carbon-900/90 backdrop-blur-md sticky top-0 z-30 flex items-center justify-between px-6 md:px-8">
        {/* Left Telemetry Indicators */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Radio className="w-3.5 h-3.5 text-laser-emerald animate-pulse" />
            <span className="text-[11px] font-mono tracking-widest text-slate-400 uppercase">
              GATEWAY:
            </span>
            <span className="text-[11px] font-mono text-slate-200 bg-carbon-800 px-2 py-0.5 rounded-sm border border-carbon-700">
              HTTP/2 // 0.0.0.0:8000
            </span>
          </div>

          <div className="hidden lg:flex items-center gap-2">
            <span className="text-[11px] font-mono tracking-widest text-slate-400 uppercase">
              EMBEDDER:
            </span>
            <span className="text-[11px] font-mono text-laser-cyan bg-laser-cyan/10 px-2 py-0.5 rounded-sm border border-laser-cyan/20">
              FASTEMBED // BGE-SMALL-EN-V1.5 (384D)
            </span>
          </div>
        </div>

        {/* Right Controls & Clock */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-slate-400 bg-carbon-950 px-2.5 py-1 rounded-sm border border-carbon-750">
            <Clock className="w-3 h-3 text-slate-400" />
            <span className="tabular-nums">{time || "2026-09-28 00:00:00 UTC"}</span>
          </div>

          <button
            onClick={() => setIsOpen(true)}
            className="flex items-center gap-2 text-xs font-mono bg-carbon-800 hover:bg-carbon-750 text-slate-200 hover:text-white px-3 py-1.5 rounded-sm border border-carbon-700 transition-colors shadow-sm"
          >
            <KeyRound className="w-3.5 h-3.5 text-laser-emerald" />
            <span>GATEWAY AUTH</span>
          </button>
        </div>
      </header>

      {/* Industrial Key Modal */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-carbon-900 border border-carbon-700 rounded-sm w-full max-w-lg p-6 shadow-2xl space-y-5 industrial-panel">
            <div className="flex items-center justify-between pb-3 border-b border-carbon-750">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-laser-emerald" />
                <div>
                  <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                    GATEWAY ACCESS CREDENTIALS
                  </h3>
                  <p className="text-[11px] font-mono text-slate-400">
                    Scoped API authorization for tenant inference and master provisioning
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-slate-400 hover:text-white p-1 hover:bg-carbon-800 rounded-sm transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs font-mono">
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-slate-400 uppercase tracking-wider text-[10px] font-semibold">
                    TENANT INFERENCE KEY (`X-API-Key` or `Bearer`)
                  </label>
                  <span className="text-[10px] text-laser-cyan">INFERENCE SCOPE</span>
                </div>
                <input
                  type="text"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="cm_live_..."
                  className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-cyan"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-slate-400 uppercase tracking-wider text-[10px] font-semibold">
                    MASTER ADMIN SECRET (`/v1/admin/*` & `/v1/cache/*`)
                  </label>
                  <span className="text-[10px] text-laser-amber">ADMIN SCOPE</span>
                </div>
                <input
                  type="password"
                  value={adminKey}
                  onChange={(e) => setAdminKey(e.target.value)}
                  placeholder="cm_admin_..."
                  className="w-full bg-carbon-950 border border-carbon-750 rounded-sm px-3 py-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-laser-amber"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-carbon-750 flex justify-end gap-2.5 font-mono text-xs">
              <button
                onClick={() => setIsOpen(false)}
                className="px-4 py-2 text-slate-400 hover:text-white hover:bg-carbon-800 rounded-sm transition-colors"
              >
                DISMISS
              </button>
              <button
                onClick={handleSaveKeys}
                className="flex items-center gap-1.5 px-4 py-2 bg-laser-emerald text-carbon-950 font-bold hover:bg-emerald-400 rounded-sm transition-colors shadow-sm"
              >
                <Check className="w-3.5 h-3.5" />
                SAVE CREDENTIALS
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
