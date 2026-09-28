"use client";

import { useState, useEffect } from "react";
import toast, { Toaster } from "react-hot-toast";

export default function Navbar() {
  const [apiKey, setApiKey] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setApiKey(localStorage.getItem("cachemind_api_key") || "cm_live_development_test_key_000000000000000000000000");
    setAdminKey(localStorage.getItem("cachemind_admin_key") || "cm_admin_master_secret_key_9999999999999999");
  }, []);

  const handleSaveKeys = () => {
    localStorage.setItem("cachemind_api_key", apiKey.trim());
    localStorage.setItem("cachemind_admin_key", adminKey.trim());
    toast.success("Gateway authentication keys saved!");
    setIsOpen(false);
  };

  return (
    <>
      <Toaster position="top-right" toastOptions={{ style: { background: "#1F2937", color: "#fff" } }} />
      <header className="h-16 border-b border-dark-border bg-dark-card/50 backdrop-blur-md sticky top-0 z-30 flex items-center justify-between px-8">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span>Environment:</span>
            <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-400 border border-blue-800/40 text-xs font-mono">
              development (FastEmbed + Redis L1)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsOpen(true)}
            className="flex items-center gap-2 text-xs bg-dark-bg hover:bg-dark-hover text-gray-300 px-3.5 py-1.5 rounded-lg border border-dark-border transition-colors"
          >
            <span>🔑</span>
            <span>Gateway Credentials</span>
          </button>
        </div>
      </header>

      {/* Settings / Keys Modal */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-dark-card border border-dark-border rounded-xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-dark-border">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <span>⚙️</span> Gateway Authorization Settings
              </h3>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Tenant API Key (Inference & Client API)
                </label>
                <input
                  type="text"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="cm_live_..."
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Master Admin Secret Key (/v1/admin/* Provisioning)
                </label>
                <input
                  type="password"
                  value={adminKey}
                  onChange={(e) => setAdminKey(e.target.value)}
                  placeholder="cm_admin_..."
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-dark-border flex justify-end gap-2">
              <button
                onClick={() => setIsOpen(false)}
                className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveKeys}
                className="px-4 py-2 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
              >
                Save Credentials
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
