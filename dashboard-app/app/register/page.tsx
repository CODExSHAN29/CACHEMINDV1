"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  Sparkles,
  Cpu,
  UserPlus,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Mail,
  Lock,
  Building,
  User as UserIcon,
} from "lucide-react";

function GithubIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
      />
    </svg>
  );
}

export default function RegisterPage() {
  const router = useRouter();
  const { signup, loginWithGithub } = useAuth();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [org, setOrg] = useState("");
  const [password, setPassword] = useState("");
  const [tier, setTier] = useState<"developer" | "growth" | "enterprise">("growth");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !password.trim()) {
      setErrorMsg("Please fill out all required fields.");
      return;
    }

    setIsLoading(true);
    setErrorMsg("");

    try {
      await signup(name.trim(), email.trim(), password.trim(), org.trim() || `${name}'s Org`, tier);
      router.push("/dashboard");
    } catch (err: any) {
      setErrorMsg(err?.message || "Registration failed.");
      setIsLoading(false);
    }
  };

  const handleGithubSignUp = async () => {
    setIsLoading(true);
    setErrorMsg("");
    try {
      await loginWithGithub();
      router.push("/dashboard");
    } catch (err: any) {
      setErrorMsg(err?.message || "GitHub authentication failed.");
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#07090e] flex items-center justify-center px-4 sm:px-6 py-10 relative overflow-hidden selection:bg-indigo-500/30 selection:text-indigo-100">
      {/* Ambient background glow */}
      <div className="absolute top-1/4 right-1/4 w-[450px] h-[450px] bg-indigo-600/15 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/4 w-[350px] h-[350px] bg-cyan-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b10_1px,transparent_1px),linear-gradient(to_bottom,#1e293b10_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

      <div className="relative z-10 w-full max-w-lg bg-slate-950/90 border border-slate-800/80 backdrop-blur-2xl shadow-[0_0_50px_rgba(99,102,241,0.08)] p-6 sm:p-8">
        {/* Header Badge & Brand */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 bg-indigo-950/90 border border-indigo-600/60 flex items-center justify-center text-indigo-400 group-hover:border-indigo-400 group-hover:shadow-[0_0_15px_rgba(99,102,241,0.5)] transition-all">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <h2 className="font-display font-bold text-lg text-slate-100 tracking-tight leading-tight">
                  CacheMind
                </h2>
                <p className="text-[9px] font-mono text-indigo-400 tracking-widest">
                  TENANT PROVISIONING v1.4
                </p>
              </div>
            </Link>

            <span className="text-[10px] font-mono font-bold text-emerald-400 bg-emerald-950/80 border border-emerald-800 px-2 py-0.5">
              INSTANT KEY ALLOCATION
            </span>
          </div>

          <h1 className="font-display font-bold text-2xl text-slate-100 tracking-tight">
            Provision Organization Tenant
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-1">
            Get instant developer access to CacheMind with 500,000 free queries / month.
          </p>
        </div>

        {errorMsg && (
          <div className="mb-5 p-3 bg-rose-950/60 border border-rose-900 text-rose-300 text-xs font-mono">
            {errorMsg}
          </div>
        )}

        {/* GitHub 1-Click Fast Track */}
        <button
          type="button"
          onClick={handleGithubSignUp}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2.5 py-3 px-4 bg-slate-900 hover:bg-slate-800/90 border border-slate-700 text-slate-100 hover:border-slate-500 font-mono text-xs font-semibold transition-all shadow-sm mb-5 group"
        >
          {isLoading ? (
            <div className="w-4 h-4 border-2 border-slate-400 border-t-white rounded-full animate-spin" />
          ) : (
            <GithubIcon className="w-4 h-4 text-slate-200 group-hover:scale-105 transition-transform" />
          )}
          <span>SIGN UP WITH GITHUB SSO</span>
        </button>

        {/* Divider */}
        <div className="relative flex py-2 items-center mb-5">
          <div className="flex-grow border-t border-slate-800"></div>
          <span className="flex-shrink mx-4 text-[10px] font-mono text-slate-500 uppercase tracking-wider">
            OR CREATE CUSTOM WORKSPACE
          </span>
          <div className="flex-grow border-t border-slate-800"></div>
        </div>

        <form className="space-y-4" onSubmit={handleRegister}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="reg-name"
                className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5"
              >
                <UserIcon className="w-3 h-3 text-indigo-400" />
                <span>Full Name</span>
              </label>
              <input
                id="reg-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Dr. Jane Doe"
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-600"
                required
              />
            </div>
            <div>
              <label
                htmlFor="reg-org"
                className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5"
              >
                <Building className="w-3 h-3 text-indigo-400" />
                <span>Organization</span>
              </label>
              <input
                id="reg-org"
                type="text"
                value={org}
                onChange={(e) => setOrg(e.target.value)}
                placeholder="Anthropic Labs"
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-600"
                required
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="reg-email"
              className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5"
            >
              <Mail className="w-3 h-3 text-indigo-400" />
              <span>Work Email</span>
            </label>
            <input
              id="reg-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@anthropic.com"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-600"
              required
            />
          </div>

          <div>
            <label
              htmlFor="reg-password"
              className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5"
            >
              <Lock className="w-3 h-3 text-indigo-400" />
              <span>Password</span>
            </label>
            <input
              id="reg-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••••••••••"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-600"
              required
            />
          </div>

          <div className="p-3 bg-slate-900/60 border border-slate-800/80 space-y-1">
            <div className="text-[10px] font-mono text-slate-400 font-bold uppercase tracking-wider">
              Selected Plan Tier:
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-indigo-300 font-bold">
                Developer Free Tier (500k queries/mo)
              </span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 border border-emerald-800 px-2 py-0.5">
                $0.00 / mo
              </span>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full btn-primary text-xs font-mono flex items-center justify-center gap-2 py-3 shadow-xl shadow-indigo-900/30 mt-2"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            ) : (
              <UserPlus className="w-4 h-4" />
            )}
            <span>PROVISION TENANT & LAUNCH CONSOLE</span>
          </button>
        </form>

        {/* Links */}
        <div className="mt-6 pt-4 border-t border-slate-900 flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span>Already have an account?</span>
          <Link
            href="/login"
            className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold"
          >
            Sign In <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </main>
  );
}
