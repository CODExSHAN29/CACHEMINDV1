"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Square, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
const CacheRibbon = dynamic(() => import("./three/CacheRibbon"), { ssr: false });
export default function AuthScreen({ signupMode = false }: { signupMode?: boolean }) {
  const { signup, loginWithEmail, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    if (signupMode && password !== form.get("confirm")) { setError("Passwords do not match."); return; }
    setLoading(true); setError("");
    try {
      const email = String(form.get("email")).trim();
      const ok = signupMode ? await signup(String(form.get("name")).trim(), email, password, String(form.get("workspace")).trim()) : await loginWithEmail(email, password);
      if (ok) router.push("/dashboard"); else setError(signupMode ? "Account creation failed. Check your details and try again." : "Invalid email or password.");
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to connect. Please try again."); }
    finally { setLoading(false); }
  }
  const fields = signupMode ? [{ key: "name", label: "Full name", type: "text", auto: "name" }, { key: "email", label: "Email address", type: "email", auto: "email" }, { key: "workspace", label: "Workspace name", type: "text", auto: "organization" }, { key: "password", label: "Password", type: "password", auto: "new-password" }, { key: "confirm", label: "Confirm password", type: "password", auto: "new-password" }] : [{ key: "email", label: "Email address", type: "email", auto: "email" }, { key: "password", label: "Password", type: "password", auto: "current-password" }];
  return <main className="auth-layout"><section className="auth-story"><CacheRibbon mode={signupMode ? 1 : 0} /><Link className="wordmark" href="/"><Square fill="currentColor" /><span>CACHEMIND</span></Link><div className="auth-story-copy"><div className="section-index">{signupMode ? "02 / Provision your workspace" : "01 / Return to memory"}</div><h2 className="editorial">Persistent memory<br />for repeated<br /><em className="text-primary-bright">intelligence.</em></h2><p>A precise interface to your gateway. Inspect requests, manage credentials, and measure what your application reuses.</p></div><div className="auth-story-footer">{signupMode ? <><span>ON CREATION / ACCOUNT IDENTITY</span><span>WORKSPACE / DEFAULT PROJECT</span><span>CREATE A GATEWAY CREDENTIAL IN THE CONSOLE</span></> : <><span>AUTHENTICATED WORKSPACE ACCESS</span><span>REUSE BEFORE RECOMPUTE.</span></>}</div></section><section className="auth-form-section"><div className="auth-form"><div className="section-index">{signupMode ? "Account / Create" : "Account / Access"}</div><h1>{signupMode ? "Create a workspace" : "Sign in"}</h1><p>{signupMode ? "Set up your account and isolated gateway workspace." : "Continue to your CacheMind control plane."}</p>{error && <div role="alert" className="alert-error">{error}</div>}<form onSubmit={submit}>{fields.map(field => <div key={field.key} className="auth-field"><label htmlFor={field.key} className="label-caps">{field.label}</label><input id={field.key} name={field.key} type={field.type} autoComplete={field.auto} required className="input-field" /></div>)}<button disabled={loading} className="btn-primary" type="submit">{loading ? "Please wait…" : signupMode ? "Create workspace" : "Sign in"}<ArrowRight size={14} /></button></form><div className="auth-form-footer"><span>{signupMode ? "Already have an account?" : "New to CacheMind?"}</span><Link href={signupMode ? "/login" : "/signup"}>{signupMode ? "Sign in" : "Create account"} <ArrowRight size={12} className="inline" /></Link></div></div></section></main>;
}
