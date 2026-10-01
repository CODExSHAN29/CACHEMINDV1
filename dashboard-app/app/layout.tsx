import "./globals.css";
import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Instrument_Serif } from "next/font/google";
import { AuthProvider } from "@/context/AuthContext";
import AppShell from "@/components/AppShell";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });
const instrumentSerif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-editorial", display: "swap" });

export const metadata: Metadata = {
  title: "CacheMind — Semantic Caching for AI Applications",
  description: "Exact and semantic caching for LLM APIs, with tenant isolation, guardrails, and measured telemetry.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} ${instrumentSerif.variable} dark`}>
      <body className="font-sans antialiased">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
