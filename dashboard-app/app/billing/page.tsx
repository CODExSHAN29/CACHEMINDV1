"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { BillingPlan, SubscriptionInfo } from "@/lib/types";

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
      toast.success(`Upgraded to ${tier.toUpperCase()} plan! Stripe webhook initialized.`);
      refreshData();
    } catch (e: any) {
      toast.error(`Subscription failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Billing & Subscription Tiers</h2>
        <p className="text-sm text-gray-400 mt-1">
          Manage commercial subscription plans, rate limits, and Stripe metered billing usage.
        </p>
      </div>

      {/* Subscription Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {plans.map((p) => {
          const isPro = p.tier === "pro";
          return (
            <div
              key={p.tier}
              className={`rounded-xl p-6 border flex flex-col justify-between transition-all duration-200 ${
                isPro
                  ? "bg-gradient-to-b from-blue-950/40 to-dark-card border-blue-500/50 shadow-xl shadow-blue-500/10"
                  : "bg-dark-card border-dark-border"
              }`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-white uppercase tracking-wider">{p.name}</h3>
                  {isPro && (
                    <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-600 text-white">
                      Recommended
                    </span>
                  )}
                </div>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold text-white">${p.monthly_price_usd}</span>
                  <span className="text-xs text-gray-400">/ month</span>
                </div>

                <ul className="mt-6 space-y-3 text-xs text-gray-300">
                  <li className="flex items-center gap-2">
                    <span className="text-blue-400">✓</span>
                    <span>
                      Daily Limit:{" "}
                      <strong className="text-white font-mono">
                        {p.daily_request_limit > 0 ? p.daily_request_limit.toLocaleString() : "Unlimited"}
                      </strong>{" "}
                      reqs
                    </span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-blue-400">✓</span>
                    <span>
                      Token Cap:{" "}
                      <strong className="text-white font-mono">
                        {p.daily_token_limit > 0 ? p.daily_token_limit.toLocaleString() : "Unlimited"}
                      </strong>{" "}
                      tokens/day
                    </span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-blue-400">✓</span>
                    <span>
                      Cache Retention: <strong className="text-white font-mono">{p.cache_ttl_days} days</strong>
                    </span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-blue-400">✓</span>
                    <span>
                      Overage: <strong className="text-white font-mono">${p.overage_per_1k_requests_usd}</strong> / 1K reqs
                    </span>
                  </li>
                </ul>
              </div>

              <div className="mt-8">
                <button
                  onClick={() => handleSubscribe(p.tier)}
                  disabled={loading}
                  className={`w-full py-2.5 rounded-lg text-xs font-semibold transition-all ${
                    isPro
                      ? "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-500/20"
                      : "bg-dark-bg hover:bg-dark-hover text-gray-200 border border-dark-border"
                  }`}
                >
                  {loading ? "Processing..." : `Select ${p.name}`}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active Subscriptions List */}
      <div className="bg-dark-card border border-dark-border rounded-xl p-6 space-y-4">
        <h3 className="text-base font-semibold text-white">Active Tenant Subscriptions</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-300">
            <thead className="bg-dark-bg/60 text-xs text-gray-400 uppercase tracking-wider border-b border-dark-border">
              <tr>
                <th className="py-3 px-4">Tenant ID</th>
                <th className="py-3 px-4">Current Plan</th>
                <th className="py-3 px-4">Monthly Rate</th>
                <th className="py-3 px-4">Daily Request Limit</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border/60">
              {subscriptions.map((s) => (
                <tr key={s.tenant_id} className="hover:bg-dark-hover/50">
                  <td className="py-3.5 px-4 font-mono text-xs text-white">{s.tenant_id}</td>
                  <td className="py-3.5 px-4 font-semibold text-blue-400 uppercase text-xs">{s.tier}</td>
                  <td className="py-3.5 px-4 font-mono text-xs">${s.monthly_price_usd.toFixed(2)}/mo</td>
                  <td className="py-3.5 px-4 font-mono text-xs">
                    {s.daily_request_limit > 0 ? s.daily_request_limit.toLocaleString() : "Unlimited"}
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="text-xs text-emerald-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
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
