"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { BillingPlan, SubscriptionInfo } from "@/lib/types";
import {
  CreditCard,
  Zap,
  ShieldCheck,
  Check,
  Coins,
  ArrowUpRight,
  Layers,
} from "lucide-react";

export default function BillingPage() {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionInfo[]>([]);
  const [loading, setLoading] = useState(false);

  const refreshData = async () => {
    try {
      const pList = await api.listPlans();
      setPlans(pList);
      const sList = await api.listSubscriptions();
      setSubscriptions(sList);
    } catch (e: any) {
      console.error(e);
    }
  };

  useEffect(() => {
    refreshData();
  }, []);

  const handleSubscribe = async (tier: string) => {
    setLoading(true);
    try {
      await api.subscribeTenant("tenant_default", tier);
      toast.success(`Upgraded to ${tier.toUpperCase()} plan — Stripe metered billing initialized.`);
      refreshData();
    } catch (e: any) {
      toast.error(`Subscription failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-carbon-750/80">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-laser-cyan font-semibold">
            SYS.ZONE // 05
          </span>
          <span className="text-slate-400 font-mono text-[10px]">
            :: [METERED BILLING & COMMERCIAL TIER SELECTION]
          </span>
        </div>
        <h2 className="text-xl md:text-2xl font-mono font-bold text-white tracking-tight mt-1">
          METERED BILLING & TIER SELECTION
        </h2>
        <p className="text-xs font-mono text-slate-400 mt-0.5">
          Stripe-metered billing tiers, rate-limit quotas, cache retention windows, and overage cost structures.
        </p>
      </div>

      {/* Plan Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {plans.map((p) => {
          const isPro = p.tier === "pro";
          return (
            <div
              key={p.tier}
              className={`industrial-panel relative bg-carbon-900 border rounded-sm p-6 flex flex-col justify-between transition-all ${
                isPro
                  ? "border-laser-amber/60 shadow-[0_0_40px_-12px_rgba(255,184,0,0.15)]"
                  : "border-carbon-750/90 hover:border-carbon-600"
              }`}
            >
              {/* Corner crosshairs via CSS pseudo already handles +-; we add a laser accent stripe */}
              <div className={`absolute top-0 left-0 right-0 h-0.5 ${isPro ? "bg-gradient-to-r from-laser-amber/80 via-laser-amber to-laser-amber/30" : "bg-gradient-to-r from-carbon-600/40 to-transparent"}`} />

              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-mono font-bold text-white uppercase tracking-widest">
                    {p.name}
                  </h3>
                  {isPro && (
                    <span className="text-[9px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-sm bg-laser-amber text-carbon-950 font-extrabold shadow-sm">
                      RECOMMENDED
                    </span>
                  )}
                </div>

                <div className="flex items-baseline gap-1 mb-4">
                  <span className="text-3xl font-mono font-extrabold text-white tabular-nums">${p.monthly_price_usd}</span>
                  <span className="text-xs font-mono text-slate-400">/ month</span>
                </div>

                <div className="space-y-2.5 text-xs font-mono text-slate-300">
                  <div className="flex items-center gap-2.5 py-1 border-b border-carbon-750/40">
                    <Zap className={`w-3.5 h-3.5 ${isPro ? "text-laser-amber" : "text-laser-cyan"}`} />
                    <span>Daily Request Limit:</span>
                    <strong className="text-white tabular-nums ml-auto">{p.daily_request_limit > 0 ? p.daily_request_limit.toLocaleString() : "UNLIMITED"}</strong>
                  </div>
                  <div className="flex items-center gap-2.5 py-1 border-b border-carbon-750/40">
                    <Layers className="w-3.5 h-3.5 text-laser-emerald" />
                    <span>Token Cap:</span>
                    <strong className="text-white tabular-nums ml-auto">{p.daily_token_limit > 0 ? p.daily_token_limit.toLocaleString() : "UNLIMITED"}</strong>
                  </div>
                  <div className="flex items-center gap-2.5 py-1 border-b border-carbon-750/40">
                    <ShieldCheck className="w-3.5 h-3.5 text-laser-cyan" />
                    <span>Cache Retention:</span>
                    <strong className="text-white tabular-nums ml-auto">{p.cache_ttl_days} DAYS</strong>
                  </div>
                  <div className="flex items-center gap-2.5 py-1">
                    <Coins className="w-3.5 h-3.5 text-laser-amber" />
                    <span>Overage:</span>
                    <strong className="text-white tabular-nums ml-auto">${p.overage_per_1k_requests_usd} / 1K REQ</strong>
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleSubscribe(p.tier)}
                disabled={loading}
                className={`mt-5 w-full py-2.5 rounded-sm text-xs font-mono font-bold uppercase tracking-widest transition-colors flex items-center justify-center gap-2 ${
                  isPro
                    ? "bg-laser-amber text-carbon-950 hover:bg-amber-300 shadow-[0_0_20px_-4px_rgba(255,184,0,0.25)]"
                    : "bg-carbon-800 border border-carbon-700 text-slate-200 hover:bg-carbon-750 hover:border-carbon-600"
                }`}
              >
                {loading ? "PROCESSING..." : `SELECT ${p.name}`}
                <ArrowUpRight className="w-3 h-3" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Active Subscriptions */}
      <div className="industrial-panel bg-carbon-900 border border-carbon-750/90 rounded-sm p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-carbon-750/70">
          <div className="flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-laser-cyan" />
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              ACTIVE SUBSCRIPTION REGISTRY
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">PARTITION: [TENANT_DEFAULT]</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-300">
            <thead className="bg-carbon-950 text-[10px] text-slate-400 uppercase tracking-wider border-b border-carbon-750">
              <tr>
                <th className="py-2.5 px-4">TENANT ID</th>
                <th className="py-2.5 px-4">PLAN TIER</th>
                <th className="py-2.5 px-4">MONTHLY RATE</th>
                <th className="py-2.5 px-4">DAILY LIMIT</th>
                <th className="py-2.5 px-4">STATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-carbon-750/60">
              {subscriptions.map((s) => (
                <tr key={s.tenant_id} className="hover:bg-carbon-850/60 transition-colors">
                  <td className="py-3 px-4 font-mono text-xs text-white font-semibold">{s.tenant_id}</td>
                  <td className="py-3 px-4 font-mono text-[11px] text-laser-cyan font-bold uppercase">{s.tier}</td>
                  <td className="py-3 px-4 font-mono text-xs tabular-nums">${s.monthly_price_usd.toFixed(2)}/mo</td>
                  <td className="py-3 px-4 font-mono text-xs tabular-nums text-slate-200">{s.daily_request_limit > 0 ? s.daily_request_limit.toLocaleString() : "UNLIMITED"}</td>
                  <td className="py-3 px-4">
                    <span className="text-[11px] font-mono font-bold text-laser-emerald flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-laser-emerald animate-pulse"></span>
                      {s.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
