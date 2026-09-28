import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "CacheMind Developer Portal & Gateway Console",
  description: "Enterprise Semantic Caching Gateway & Observability Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-dark-bg text-gray-100 flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <Navbar />
          <main className="p-8 max-w-7xl mx-auto w-full">{children}</main>
        </div>
      </body>
    </html>
  );
}
