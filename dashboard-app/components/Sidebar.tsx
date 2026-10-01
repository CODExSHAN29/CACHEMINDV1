"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Square } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
const items = [["Overview", "/dashboard"], ["Analytics", "/analytics"], ["Cache", "/cache"], ["Playground", "/playground"], ["Keys", "/keys"], ["Billing", "/billing"]];
export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const { activeWorkspace } = useAuth();
  return <aside className="console-sidebar"><Link href="/" onClick={onNavigate} className="wordmark"><Square fill="currentColor" /><span>CACHEMIND</span></Link><nav className="console-nav" aria-label="Console navigation">{items.map(([label, href], index) => <Link key={href} href={href} title={label} onClick={onNavigate} aria-current={path === href ? "page" : undefined}><span>0{index + 1}</span><div className="nav-label">{label}</div></Link>)}</nav><div className="sidebar-foot">CONTROL PLANE<br /><span className="text-on-surface break-all">{activeWorkspace?.name ?? "No workspace selected"}</span><br />TENANT ISOLATED / SESSION AUTH</div></aside>;
}
