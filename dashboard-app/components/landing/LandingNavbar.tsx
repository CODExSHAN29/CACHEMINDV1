"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowRight, Menu, X, Cpu } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function LandingNavbar() {
  const { user, isAuthenticated } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-[#07090e]/90 backdrop-blur-md border-b border-slate-800/80 shadow-2xl shadow-indigo-950/20"
          : "bg-transparent border-b border-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 sm:h-20 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-none bg-indigo-600/20 border border-indigo-500/50 flex items-center justify-center text-indigo-400 group-hover:border-indigo-400 group-hover:shadow-[0_0_15px_rgba(99,102,241,0.5)] transition-all">
            <Cpu className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <span className="font-display font-bold text-lg text-slate-100 tracking-tight flex items-center gap-1.5">
              CACHEMIND
              <span className="text-[10px] font-mono px-1.5 py-0.2 bg-indigo-950/80 text-indigo-400 border border-indigo-800/60 font-medium">
                v1.4
              </span>
            </span>
            <span className="text-[9px] font-mono text-slate-500 tracking-wider uppercase -mt-0.5">
              PRECISION SEMANTIC GATEWAY
            </span>
          </div>
        </Link>

        {/* Desktop Nav Items */}
        <nav className="hidden md:flex items-center gap-8">
          <a
            href="#benchmarks"
            className="text-xs font-mono text-slate-300 hover:text-indigo-400 transition-colors uppercase tracking-wider"
          >
            // Benchmarks
          </a>
          <a
            href="#architecture"
            className="text-xs font-mono text-slate-300 hover:text-indigo-400 transition-colors uppercase tracking-wider"
          >
            // Architecture
          </a>
          <a
            href="#interactive-demo"
            className="text-xs font-mono text-slate-300 hover:text-indigo-400 transition-colors uppercase tracking-wider"
          >
            // 3D Vector Space
          </a>
          <a
            href="#roi-calculator"
            className="text-xs font-mono text-slate-300 hover:text-indigo-400 transition-colors uppercase tracking-wider"
          >
            // ROI Model
          </a>
          <a
            href="#pricing"
            className="text-xs font-mono text-slate-300 hover:text-indigo-400 transition-colors uppercase tracking-wider"
          >
            // Pricing
          </a>
        </nav>

        {/* Action CTAs */}
        <div className="hidden sm:flex items-center gap-3">
          {isAuthenticated ? (
            <Link
              href="/dashboard"
              className="btn-primary text-xs font-mono flex items-center gap-2"
            >
              OPEN CONSOLE
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="text-xs font-mono px-3.5 py-2 text-slate-300 hover:text-white bg-slate-900/60 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 transition-all flex items-center gap-1.5"
              >
                SIGN IN
              </Link>
              <Link
                href="/signup"
                className="btn-primary text-xs font-mono flex items-center gap-2"
              >
                GET STARTED
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </>
          )}
        </div>

        {/* Mobile menu trigger */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 text-slate-400 hover:text-slate-100"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Menu dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-slate-950/95 border-b border-slate-800 p-6 space-y-4 backdrop-blur-xl">
          <a
            href="#benchmarks"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-xs font-mono text-slate-300 uppercase"
          >
            // Benchmarks
          </a>
          <a
            href="#architecture"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-xs font-mono text-slate-300 uppercase"
          >
            // Architecture
          </a>
          <a
            href="#interactive-demo"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-xs font-mono text-slate-300 uppercase"
          >
            // 3D Vector Space
          </a>
          <a
            href="#roi-calculator"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-xs font-mono text-slate-300 uppercase"
          >
            // ROI Model
          </a>
          <a
            href="#pricing"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-xs font-mono text-slate-300 uppercase"
          >
            // Pricing
          </a>
          <div className="pt-4 border-t border-slate-800 flex flex-col gap-3">
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full btn-primary text-xs font-mono text-center justify-center py-2.5"
              >
                OPEN CONSOLE
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full text-xs font-mono py-2.5 bg-slate-900 text-slate-200 border border-slate-800 text-center"
                >
                  SIGN IN
                </Link>
                <Link
                  href="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full btn-primary text-xs font-mono text-center justify-center py-2.5"
                >
                  GET STARTED
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
