"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export interface User {
  id: string;
  name: string;
  email: string;
  organization: string;
  role: "admin" | "developer" | "viewer";
  avatarUrl?: string;
  provider?: "email" | "github";
}

export interface Workspace {
  id: string;
  name: string;
  role: string;
}

export interface ProjectInfo {
  id: string;
  name: string;
  tenant_id: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  projects: ProjectInfo[];
  activeProject: ProjectInfo | null;
  login: (email: string, pass: string) => Promise<boolean>;
  loginWithEmail: (email: string, pass: string) => Promise<boolean>;
  signup: (name: string, email: string, pass: string, org: string, tier?: string) => Promise<boolean>;
  logout: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => Promise<void>;
  switchProject: (projectId: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectInfo | null>(null);
  const router = useRouter();

  const refreshWorkspaces = useCallback(async () => {
    try {
      const list = await api.listWorkspaces();
      const mapped: Workspace[] = (Array.isArray(list) ? list : []).map((w: any) => ({
        id: w.id || w.tenant_id,
        name: w.name || w.tenant_name || "Workspace",
        role: w.role || "developer",
      }));
      setWorkspaces(mapped);
      return mapped;
    } catch { return []; }
  }, []);

  const loadSession = useCallback(async () => {
    try {
      const me = await api.getMe();
      if (me && me.user) {
        const authUser: User = {
          id: me.user.id,
          name: me.user.full_name || me.user.email.split("@")[0],
          email: me.user.email,
          organization: me.active_tenant?.name || "My Workspace",
          role: (me.active_tenant?.role as any) || "admin",
          provider: "email",
        };
        setUser(authUser);
        const wsList = await refreshWorkspaces();
        const currentWs = wsList.find((w) => w.id === (me.active_tenant?.id || me.active_workspace?.id));
        if (currentWs) setActiveWorkspace(currentWs);
        else if (wsList.length) { setActiveWorkspace(wsList[0]); }
      } else {
        setUser(null);
        setWorkspaces([]);
        setActiveWorkspace(null);
      }
    } catch {
      setUser(null);
      setWorkspaces([]);
      setActiveWorkspace(null);
    } finally {
      setIsLoading(false);
    }
  }, [refreshWorkspaces]);

  useEffect(() => {
    loadSession();
    const interval = setInterval(() => loadSession(), 30000);
    return () => clearInterval(interval);
  }, [loadSession]);

  useEffect(() => {
    if (!activeWorkspace || !user) { setProjects([]); setActiveProject(null); return; }
    api.listProjects(activeWorkspace.id).then((list) => {
      const mapped = (Array.isArray(list) ? list : []).map((p: any) => ({
        id: p.id || p.project_id,
        name: p.name || "Project",
        tenant_id: p.tenant_id || activeWorkspace.id,
      }));
      setProjects(mapped);
      if (mapped.length && !activeProject) setActiveProject(mapped[0]);
    }).catch(() => { setProjects([]); setActiveProject(null); });
  }, [activeWorkspace, user, activeProject]);

  const loginWithEmail = async (email: string, pass: string): Promise<boolean> => {
    const res = await api.login({ email, password: pass });
    if (res && res.user) {
      const loggedUser: User = {
        id: res.user.id,
        name: res.user.full_name || email.split("@")[0],
        email: res.user.email,
        organization: res.active_tenant?.name || "My Workspace",
        role: (res.active_tenant?.role as any) || "admin",
        provider: "email",
      };
      setUser(loggedUser);
      const wsList = await refreshWorkspaces();
      const currentWs = wsList.find((w) => w.id === (res.active_tenant?.id || res.active_workspace?.id)) || wsList[0] || null;
      setActiveWorkspace(currentWs);
      return true;
    }
    return false;
  };

  const login = async (email: string, pass: string): Promise<boolean> => loginWithEmail(email, pass);

  const signup = async (name: string, email: string, pass: string, org: string, tier = "growth"): Promise<boolean> => {
    const res = await api.signup({ email, password: pass, full_name: name, workspace_name: org });
    if (res && res.user) {
      const newUser: User = {
        id: res.user.id,
        name: res.user.full_name || name,
        email: res.user.email,
        organization: res.active_tenant?.name || org,
        role: "admin",
        provider: "email",
      };
      setUser(newUser);
      const wsList = await refreshWorkspaces();
      const currentWs = wsList.find((w) => w.id === (res.active_tenant?.id)) || wsList[0] || null;
      setActiveWorkspace(currentWs);
      return true;
    }
    return false;
  };

  const logout = async () => {
    try { await api.logout(); } catch {}
    setUser(null);
    setWorkspaces([]);
    setActiveWorkspace(null);
    setProjects([]);
    setActiveProject(null);
    router.push("/login");
  };

  const switchWorkspace = async (workspaceId: string) => {
    try { await api.selectWorkspace(workspaceId); } catch {}
    const ws = workspaces.find((w) => w.id === workspaceId);
    if (ws) setActiveWorkspace(ws);
    setActiveProject(null);
    try {
      const list = await api.listProjects(workspaceId);
      const mapped = (Array.isArray(list) ? list : []).map((p: any) => ({
        id: p.id || p.project_id,
        name: p.name || "Project",
        tenant_id: p.tenant_id || workspaceId,
      }));
      setProjects(mapped);
      if (mapped.length) setActiveProject(mapped[0]);
    } catch {}
  };

  const switchProject = (projectId: string) => {
    const proj = projects.find((p) => p.id === projectId);
    if (proj) setActiveProject(proj);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        workspaces,
        activeWorkspace,
        projects,
        activeProject,
        login,
        loginWithEmail,
        signup,
        logout,
        switchWorkspace,
        switchProject,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
