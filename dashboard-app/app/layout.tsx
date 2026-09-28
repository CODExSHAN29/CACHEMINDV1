import "./globals.css";
import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CACHEMIND // Enterprise AI Gateway & Semantic Caching Control Plane",
  description: "Sub-millisecond Exact & FastEmbed Semantic Caching Engine with Real-Time Observability & Metered Billing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable} ${spaceGrotesk.variable}`}>
      <body className="bg-carbon-950 text-slate-200 flex min-h-screen selection:bg-laser-emerald/20 selection:text-laser-emerald font-sans antialiased">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 bg-[#060709] border-l border-carbon-750/60">
          <Navbar />
          <main className="p-6 md:p-8 max-w-7xl mx-auto w-full space-y-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
