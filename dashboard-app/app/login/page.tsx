"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Cpu, LogIn, ArrowRight, Mail, Lock } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { loginWithEmail } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setErrorMsg("Please enter both email and password.");
      return;
    }

    setIsLoading(true);
    setErrorMsg("");

    try {
      const ok = await loginWithEmail(email.trim(), password.trim());
      if (ok) {
        router.push("/dashboard");
      } else {
        setErrorMsg("Invalid email or password.");
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to authenticate. Please check credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#07090e] flex items-center justify-center px-4 sm:px-6 relative overflow-hidden selection:bg-indigo-500/30 selection:text-indigo-100">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/4 w-[450px] h-[450px] bg-indigo-600/15 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[350px] h-[350px] bg-cyan-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b10_1px,transparent_1px),linear-gradient(to_bottom,#1e293b10_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

      <div className="relative z-10 w-full max-w-md bg-slate-950/90 border border-slate-800/80 backdrop-blur-2xl shadow-[0_0_50px_rgba(99,102,241,0.08)] p-6 sm:p-8">
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
                  SEMANTIC GATEWAY v1.4
                </p>
              </div>
            </Link>

            <span className="text-[10px] font-mono font-bold text-emerald-400 bg-emerald-950/80 border border-emerald-800 px-2 py-0.5">
              GATEWAY READY
            </span>
          </div>

          <h1 className="font-display font-bold text-2xl text-slate-100 tracking-tight">
            Sign In to Console
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-1">
            Access your sub-millisecond semantic cache index, live telemetry & API keys.
          </p>
        </div>

        {errorMsg && (
          <div className="mb-5 p-3 bg-rose-950/60 border border-rose-900 text-rose-300 text-xs font-mono">
            {errorMsg}
          </div>
        )}

        {/* Real Email & Password Login */}
        <form className="space-y-4" onSubmit={handleEmailLogin}>
          <div>
            <label
              htmlFor="email"
              className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5"
            >
              <Mail className="w-3 h-3 text-indigo-400" />
              <span>Email Address</span>
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="developer@organization.ai"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-600"
              required
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="password"
                className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5"
              >
                <Lock className="w-3 h-3 text-indigo-400" />
                <span>Password</span>
              </label>
            </div>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••••••"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-600"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full btn-primary text-xs font-mono flex items-center justify-center gap-2 py-3 shadow-xl shadow-indigo-900/30 mt-2"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            ) : (
              <LogIn className="w-4 h-4" />
            )}
            <span>SIGN IN WITH EMAIL</span>
          </button>
        </form>

        {/* Links */}
        <div className="mt-6 pt-4 border-t border-slate-900/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span>New to CacheMind?</span>
          <Link
            href="/signup"
            className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold"
          >
            Create Account <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </main>
  );
}
