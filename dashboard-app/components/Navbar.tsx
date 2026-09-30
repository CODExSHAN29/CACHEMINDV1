"use client";

import { useState, useEffect } from "react";
import toast, { Toaster } from "react-hot-toast";
import { KeyRound, ShieldCheck, X, Check, Clock, Radio, Cpu } from "lucide-react";

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
    toast.success("Gateway authentication credentials securely stored.");
    setIsOpen(false);
  };

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
              HTTP/2 // 0.0.0.0:8000
            </span>
          </div>

          <div className="hidden lg:flex items-center gap-2">
            <span className="label-caps">EMBEDDER:</span>
            <span className="text-[11px] font-mono text-primary bg-secondary-container px-2 py-0.5 border border-blue-200">
              FASTEMBED // BGE-SMALL-EN-V1.5 (384D)
            </span>
          </div>
        </div>

        {/* Right Controls & Clock */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-on-surface-variant bg-surface-dim px-2.5 py-1 border border-outline-variant">
            <Clock className="w-3.5 h-3.5 text-on-surface-variant" />
            <span className="tabular-nums">{time || "2026-09-28 00:00:00 UTC"}</span>
          </div>

          <button
            onClick={() => setIsOpen(true)}
            className="flex items-center gap-2 text-xs font-mono font-semibold bg-surface hover:bg-surface-dim text-on-surface px-3 py-1.5 border border-outline transition-colors"
          >
            <KeyRound className="w-3.5 h-3.5 text-primary" />
            <span>GATEWAY AUTH</span>
          </button>
        </div>
      </header>

      {/* Technical Key Modal */}
      {isOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-[1px] z-50 flex items-center justify-center p-4">
          <div className="bg-surface border-2 border-on-surface w-full max-w-lg p-6 shadow-none space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-outline">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-primary" />
                <div>
                  <h3 className="text-sm font-display font-bold text-on-surface uppercase tracking-wider">
                    GATEWAY ACCESS CREDENTIALS
                  </h3>
                  <p className="text-[11px] font-mono text-on-surface-variant">
                    Scoped API authorization for tenant inference and master provisioning
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-on-surface-variant hover:text-on-surface p-1 hover:bg-surface-dim transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs font-mono">
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-on-surface-variant uppercase tracking-wider text-[10px] font-semibold">
                    TENANT INFERENCE KEY (`X-API-Key` or `Bearer`)
                  </label>
                  <span className="text-[10px] text-primary font-semibold">INFERENCE SCOPE</span>
                </div>
                <input
                  type="text"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="cm_live_..."
                  className="w-full bg-surface border border-outline px-3 py-2 text-on-surface font-mono text-xs focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-on-surface-variant uppercase tracking-wider text-[10px] font-semibold">
                    MASTER ADMIN SECRET (`/v1/admin/*` & `/v1/cache/*`)
                  </label>
                  <span className="text-[10px] text-amber-700 font-semibold">ADMIN SCOPE</span>
                </div>
                <input
                  type="password"
                  value={adminKey}
                  onChange={(e) => setAdminKey(e.target.value)}
                  placeholder="cm_admin_..."
                  className="w-full bg-surface border border-outline px-3 py-2 text-on-surface font-mono text-xs focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-outline flex justify-end gap-2.5 font-mono text-xs">
              <button
                onClick={() => setIsOpen(false)}
                className="btn-secondary"
              >
                DISMISS
              </button>
              <button
                onClick={handleSaveKeys}
                className="btn-primary flex items-center gap-1.5"
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
