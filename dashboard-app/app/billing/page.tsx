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
      {/* Precision Dossier Header */}
      <div className="bg-surface border border-outline p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge-pill bg-primary text-white border-primary">
              SYS.ZONE // 05
            </span>
            <span className="text-on-surface-variant font-mono text-xs">
              :: [METERED BILLING & COMMERCIAL TIER SELECTION]
            </span>
          </div>
          <h1 className="text-2xl font-display font-bold text-on-surface uppercase tracking-tight mt-2">
            Metered Billing & Tier Selection
          </h1>
          <p className="text-xs font-sans text-on-surface-variant mt-1 max-w-3xl">
            Stripe-metered billing tiers, rate-limit quotas, cache retention windows, and overage cost structures.
          </p>
        </div>
      </div>

      {/* Plan Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {plans.map((p) => {
          const isPro = p.tier === "pro";
          return (
            <div
              key={p.tier}
              className={`bg-surface border p-6 flex flex-col justify-between transition-all ${
                isPro
                  ? "border-primary shadow-sm bg-blue-50/20"
                  : "border-outline hover:border-outline-variant"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-mono font-bold text-on-surface uppercase tracking-wider">
                    {p.name}
                  </h2>
                  {isPro && (
                    <span className="badge-pill bg-primary text-white border-primary text-[9px] font-bold">
                      RECOMMENDED
                    </span>
                  )}
                </div>

                <div className="flex items-baseline gap-1 mb-4">
                  <span className="text-3xl font-mono font-extrabold text-on-surface tabular-nums">
                    ${p.monthly_price_usd}
                  </span>
                  <span className="text-xs font-mono text-on-surface-variant">/ month</span>
                </div>

                <div className="space-y-2.5 text-xs font-mono text-on-surface">
                  <div className="flex items-center gap-2.5 py-1 border-b border-outline-variant">
                    <Zap className="w-3.5 h-3.5 text-primary" />
                    <span className="text-on-surface-variant">Daily Request Limit:</span>
                    <strong className="text-on-surface tabular-nums ml-auto">
                      {p.daily_request_limit > 0 ? p.daily_request_limit.toLocaleString() : "UNLIMITED"}
                    </strong>
                  </div>
                  <div className="flex items-center gap-2.5 py-1 border-b border-outline-variant">
                    <Layers className="w-3.5 h-3.5 text-secondary" />
                    <span className="text-on-surface-variant">Token Cap:</span>
                    <strong className="text-on-surface tabular-nums ml-auto">
                      {p.daily_token_limit > 0 ? p.daily_token_limit.toLocaleString() : "UNLIMITED"}
                    </strong>
                  </div>
                  <div className="flex items-center gap-2.5 py-1 border-b border-outline-variant">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-on-surface-variant">Cache Retention:</span>
                    <strong className="text-on-surface tabular-nums ml-auto">{p.cache_ttl_days} DAYS</strong>
                  </div>
                  <div className="flex items-center gap-2.5 py-1">
                    <Coins className="w-3.5 h-3.5 text-amber-600" />
                    <span className="text-on-surface-variant">Overage:</span>
                    <strong className="text-on-surface tabular-nums ml-auto">
                      ${p.overage_per_1k_requests_usd} / 1K REQ
                    </strong>
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleSubscribe(p.tier)}
                disabled={loading}
                className={`btn-solid mt-5 w-full py-2.5 font-mono font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 ${
                  isPro
                    ? "bg-primary text-white border-primary hover:bg-blue-800"
                    : "bg-surface-dim border-outline text-on-surface hover:border-primary"
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
      <div className="bg-surface border border-outline p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
          <div className="flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-primary" />
            <h2 className="text-xs font-mono font-bold text-on-surface uppercase tracking-wider">
              ACTIVE SUBSCRIPTION REGISTRY
            </h2>
          </div>
          <span className="text-[10px] font-mono text-on-surface-variant bg-surface-dim px-2 py-0.5 border border-outline-variant">
            PARTITION: [TENANT_DEFAULT]
          </span>
        </div>

        <div className="overflow-x-auto border border-outline">
          <table className="w-full text-left text-xs font-mono text-on-surface">
            <thead className="bg-surface-dim text-[10px] text-on-surface-variant uppercase tracking-wider border-b border-outline">
              <tr>
                <th className="py-2.5 px-4 font-bold">TENANT ID</th>
                <th className="py-2.5 px-4 font-bold">PLAN TIER</th>
                <th className="py-2.5 px-4 font-bold">MONTHLY RATE</th>
                <th className="py-2.5 px-4 font-bold">DAILY LIMIT</th>
                <th className="py-2.5 px-4 font-bold">STATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {subscriptions.map((s) => (
                <tr key={s.tenant_id} className="hover:bg-surface-dim transition-colors">
                  <td className="py-3 px-4 font-mono text-xs text-on-surface font-semibold">{s.tenant_id}</td>
                  <td className="py-3 px-4 font-mono text-[11px] text-primary font-bold uppercase">{s.tier}</td>
                  <td className="py-3 px-4 font-mono text-xs tabular-nums">${s.monthly_price_usd.toFixed(2)}/mo</td>
                  <td className="py-3 px-4 font-mono text-xs tabular-nums text-on-surface">
                    {s.daily_request_limit > 0 ? s.daily_request_limit.toLocaleString() : "UNLIMITED"}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-[11px] font-mono font-bold text-emerald-700 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 bg-emerald-600"></span>
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
