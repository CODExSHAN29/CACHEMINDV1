"use client";
import { useEffect, useState } from "react";
const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export default function GatewayHealth() {
  const [state, setState] = useState("Checking");
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    async function check() {
      try {
        const live = await fetch(`${base}/health/live`, { signal: controller.signal });
        if (!live.ok) { if (active) setState("Unavailable"); return; }
        const ready = await fetch(`${base}/health/ready`, { signal: controller.signal });
        if (active) setState(ready.ok ? "Healthy" : "Degraded");
      } catch { if (active) setState("Unavailable"); }
    }
    check(); const interval = setInterval(check, 30000);
    return () => { active = false; controller.abort(); clearInterval(interval); };
  }, []);
  return <span className="gateway-health" data-state={state} role="status">GATEWAY / {state.toUpperCase()}</span>;
}
