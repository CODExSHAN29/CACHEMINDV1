"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useScopedData } from "@/lib/useScopedData";
import PageHeader from "@/components/PageHeader";
import { DataState } from "@/components/Telemetry";
const loadPlans = () => api.listPlans();
export default function BillingPage() {
  const [refresh, setRefresh] = useState(0);
  const plans = useScopedData(loadPlans, refresh);
  return <div><PageHeader index="06 / Billing" title="Billing Preview" description="Plan metadata from the gateway. Payment collection and subscription management are not available in this console." /><div className="hairline-panel p-6 mb-6"><span className="badge-pill text-primary-bright">PREVIEW</span><p className="text-sm text-on-surface-variant mt-4 leading-7">These plans are a product preview. Selecting a paid plan and automatic charging are unavailable. No active subscription is represented here.</p></div>{plans.loading || plans.error ? <DataState loading={plans.loading} error={plans.error} retry={() => setRefresh(v => v + 1)} /> : !plans.data?.length ? <div className="state-panel"><h3>NO PLAN METADATA</h3><p>The gateway has not returned any plans.</p></div> : <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">{plans.data.map(plan => <section className="hairline-panel p-6" key={plan.tier}><div className="section-index">{plan.name || plan.tier} / Preview</div><div className="metric-value">${plan.monthly_price_usd}<span className="text-xs text-on-surface-faint ml-2">/ month</span></div><dl className="space-y-4 mt-8 text-xs">{[["Daily requests", plan.daily_request_limit], ["Daily tokens", plan.daily_token_limit], ["Cache retention / days", plan.cache_ttl_days], ["Overage / 1K requests", `$${plan.overage_per_1k_requests_usd}`]].map(([label, value]) => <div className="flex justify-between gap-4 border-b border-border-main pb-4" key={label}><dt className="text-on-surface-variant">{label}</dt><dd className="font-mono">{value}</dd></div>)}</dl><button disabled className="btn-secondary w-full mt-8">Plan selection unavailable</button></section>)}</div>}</div>;
}
