"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Toaster } from "react-hot-toast";
import { Menu, X, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import Sidebar from "./Sidebar";
import GatewayHealth from "./GatewayHealth";
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { user, isAuthenticated, isLoading, activeWorkspace, workspaces, switchWorkspace, projects, activeProject, switchProject, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const drawer = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const isPublic = ["/", "/login", "/signup", "/register"].includes(pathname);
  useEffect(() => { if (!isLoading && !isAuthenticated && !isPublic) router.replace("/login"); }, [isLoading, isAuthenticated, isPublic, router]);
  useEffect(() => {
    if (!open) return;
    const returnFocus = trigger.current;
    const prior = document.body.style.overflow; document.body.style.overflow = "hidden";
    drawer.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
      if (event.key !== "Tab") return;
      const controls = drawer.current?.querySelectorAll<HTMLElement>("a,button");
      if (!controls?.length) return;
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = prior; document.removeEventListener("keydown", onKey); returnFocus?.focus(); };
  }, [open]);
  if (isPublic) return <>{children}</>;
  if (isLoading) return <div className="state-panel min-h-screen justify-center items-center"><span className="section-index">SESSION / LOADING</span><p>Checking your control plane session.</p></div>;
  if (!isAuthenticated) return null;
  return <div className="console-layout">
    <Toaster position="top-right" toastOptions={{ style: { background: "#0c0e14", color: "#f1f3f8", border: "1px solid #2a334c", borderRadius: "6px", fontSize: "12px" } }} />
    <div className="console-desktop-sidebar"><Sidebar /></div>
    {open && <div className="mobile-drawer" onClick={() => setOpen(false)}><div ref={drawer} role="dialog" aria-modal="true" aria-label="Navigation" onClick={e => e.stopPropagation()}><button className="absolute top-5 left-[215px] z-10" aria-label="Close navigation" onClick={() => setOpen(false)}><X size={18} /></button><Sidebar onNavigate={() => setOpen(false)} /></div></div>}
    <div className="console-workspace"><header className="console-topbar"><div className="scope-controls"><button ref={trigger} className="mobile-trigger" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}><Menu size={18} /></button><label><span className="label-caps block">Workspace</span><select aria-label="Workspace" value={activeWorkspace?.id ?? ""} onChange={e => switchWorkspace(e.target.value)}>{!workspaces.length && <option value="">No workspace</option>}{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label><span className="text-on-surface-faint">/</span><label><span className="label-caps block">Project</span><select aria-label="Project" value={activeProject?.id ?? ""} onChange={e => switchProject(e.target.value)}>{!projects.length && <option value="">No project</option>}{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label></div><div className="user-actions"><GatewayHealth /><span className="text-xs max-w-[120px] truncate">{user?.name}</span><button onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={15} /></button></div></header><main className="console-content">{children}</main></div>
  </div>;
}
