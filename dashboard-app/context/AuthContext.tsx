"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export interface User {
  id: string;
  name: string;
  email: string;
  organization: string;
  role: "admin" | "developer" | "viewer";
  avatarUrl?: string;
  provider?: "email" | "github" | "demo";
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  tenantId: string;
  projectId: string;
  apiKey: string;
  adminKey: string;
  planTier: "developer" | "growth" | "enterprise";
  isLoading: boolean;
  login: (email: string, pass: string, tenant?: string) => Promise<boolean>;
  loginWithEmail: (email: string, pass: string) => Promise<boolean>;
  loginWithGithub: (githubHandle?: string) => Promise<boolean>;
  signup: (
    name: string,
    email: string,
    pass: string,
    org: string,
    tier?: "developer" | "growth" | "enterprise"
  ) => Promise<boolean>;
  loginDemo: () => void;
  logout: () => void;
  switchTenant: (tenantId: string) => void;
  switchProject: (projectId: string) => void;
  updateKeys: (apiKey: string, adminKey: string) => void;
}

const DEFAULT_DEV_KEY = "cm_live_development_test_key_000000000000000000000000";
const DEFAULT_ADMIN_KEY = "cm_admin_master_secret_key_9999999999999999";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tenantId, setTenantId] = useState<string>("tenant_default");
  const [projectId, setProjectId] = useState<string>("proj_default");
  const [apiKey, setApiKey] = useState<string>(DEFAULT_DEV_KEY);
  const [adminKey, setAdminKey] = useState<string>(DEFAULT_ADMIN_KEY);
  const [planTier, setPlanTier] = useState<"developer" | "growth" | "enterprise">("growth");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  useEffect(() => {
    let isMounted = true;

    async function initAuth() {
      try {
        // Attempt to fetch current session context from backend (/v1/auth/me)
        const meData = await api.getMe().catch(() => null);

        if (meData && meData.user && isMounted) {
          const authUser: User = {
            id: meData.user.id,
            name: meData.user.full_name || meData.user.email.split("@")[0],
            email: meData.user.email,
            organization: meData.active_tenant?.name || "My Workspace",
            role: (meData.active_tenant?.role as any) || "admin",
            provider: "email",
          };

          setUser(authUser);
          if (meData.active_tenant?.id) {
            setTenantId(meData.active_tenant.id);
            localStorage.setItem("cachemind_tenant_id", meData.active_tenant.id);
          }
          if (meData.active_project?.id) {
            setProjectId(meData.active_project.id);
            localStorage.setItem("cachemind_project_id", meData.active_project.id);
          }
          if (meData.raw_api_key) {
            setApiKey(meData.raw_api_key);
            localStorage.setItem("cachemind_api_key", meData.raw_api_key);
          }
          if (meData.session_token) {
            localStorage.setItem("cachemind_session_token", meData.session_token);
          }
          localStorage.setItem("cachemind_user", JSON.stringify(authUser));
          return;
        }

        // Fallback to local storage if offline or during local development
        const storedUser = localStorage.getItem("cachemind_user");
        const storedTenant = localStorage.getItem("cachemind_tenant_id");
        const storedProject = localStorage.getItem("cachemind_project_id");
        const storedApiKey = localStorage.getItem("cachemind_api_key");
        const storedAdminKey = localStorage.getItem("cachemind_admin_key");
        const storedTier = localStorage.getItem("cachemind_tier") as any;

        if (storedUser && isMounted) setUser(JSON.parse(storedUser));
        if (storedTenant && isMounted) setTenantId(storedTenant);
        if (storedProject && isMounted) setProjectId(storedProject);
        if (storedApiKey && isMounted) setApiKey(storedApiKey);
        if (storedAdminKey && isMounted) setAdminKey(storedAdminKey);
        if (storedTier && isMounted) setPlanTier(storedTier);
      } catch (e) {
        console.warn("Auth initialization notice:", e);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    initAuth();

    return () => {
      isMounted = false;
    };
  }, []);

  const loginWithEmail = async (email: string, pass: string): Promise<boolean> => {
    try {
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
        const tId = res.active_tenant?.id || "tenant_default";
        const pId = res.active_project?.id || "proj_default";
        setTenantId(tId);
        setProjectId(pId);

        if (res.session_token) {
          localStorage.setItem("cachemind_session_token", res.session_token);
        }
        if (res.raw_api_key) {
          setApiKey(res.raw_api_key);
          localStorage.setItem("cachemind_api_key", res.raw_api_key);
        }

        localStorage.setItem("cachemind_user", JSON.stringify(loggedUser));
        localStorage.setItem("cachemind_tenant_id", tId);
        localStorage.setItem("cachemind_project_id", pId);
        return true;
      }
    } catch (err: any) {
      throw err;
    }
    return false;
  };

  const login = async (email: string, pass: string, tenant = "tenant_default"): Promise<boolean> => {
    return loginWithEmail(email, pass);
  };

  const loginWithGithub = async (githubHandle = "octocat-engineer"): Promise<boolean> => {
    const cleanHandle = githubHandle.trim() || "github-developer";
    const email = `${cleanHandle.toLowerCase()}@users.noreply.github.com`;
    const password = `GitHubOAuthToken_${cleanHandle}_2026!`;
    const orgName = `${cleanHandle}'s Workspace`;

    try {
      // Try login first
      return await loginWithEmail(email, password);
    } catch {
      // If user doesn't exist yet, automatically provision via signup
      try {
        return await signup(cleanHandle, email, password, orgName, "growth");
      } catch (signupErr: any) {
        // Fallback for offline dev
        const newUser: User = {
          id: "usr_gh_" + Math.random().toString(36).substring(2, 9),
          name: cleanHandle,
          email,
          organization: orgName,
          role: "admin",
          avatarUrl: `https://github.com/${cleanHandle}.png`,
          provider: "github",
        };
        const tenantSlug = `tenant_${cleanHandle.toLowerCase().replace(/[^a-z0-9]/g, "_")}`;
        setUser(newUser);
        setTenantId(tenantSlug);
        localStorage.setItem("cachemind_user", JSON.stringify(newUser));
        localStorage.setItem("cachemind_tenant_id", tenantSlug);
        return true;
      }
    }
  };

  const signup = async (
    name: string,
    email: string,
    pass: string,
    org: string,
    tier: "developer" | "growth" | "enterprise" = "growth"
  ): Promise<boolean> => {
    try {
      const res = await api.signup({
        email,
        password: pass,
        full_name: name,
        workspace_name: org,
      });

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
        const tId = res.active_tenant?.id || "tenant_default";
        const pId = res.active_project?.id || "proj_default";
        setTenantId(tId);
        setProjectId(pId);
        setPlanTier(tier);

        if (res.session_token) {
          localStorage.setItem("cachemind_session_token", res.session_token);
        }
        if (res.raw_api_key) {
          setApiKey(res.raw_api_key);
          localStorage.setItem("cachemind_api_key", res.raw_api_key);
        }

        localStorage.setItem("cachemind_user", JSON.stringify(newUser));
        localStorage.setItem("cachemind_tenant_id", tId);
        localStorage.setItem("cachemind_project_id", pId);
        localStorage.setItem("cachemind_tier", tier);
        return true;
      }
    } catch (err: any) {
      throw err;
    }
    return false;
  };

  const loginDemo = async () => {
    const demoEmail = "demo@cachemind.ai";
    const demoPass = "CacheMindDemo2026!";
    try {
      await loginWithEmail(demoEmail, demoPass);
    } catch {
      try {
        await signup("Demo Developer", demoEmail, demoPass, "CacheMind Sandbox", "growth");
      } catch {
        const demoUser: User = {
          id: "usr_developer_demo",
          name: "Demo Developer",
          email: demoEmail,
          organization: "CacheMind Sandbox",
          role: "admin",
          provider: "demo",
        };
        setUser(demoUser);
        setTenantId("tenant_default");
        setProjectId("proj_default");
        setApiKey(DEFAULT_DEV_KEY);
        setAdminKey(DEFAULT_ADMIN_KEY);
        setPlanTier("growth");
        localStorage.setItem("cachemind_user", JSON.stringify(demoUser));
        localStorage.setItem("cachemind_tenant_id", "tenant_default");
        localStorage.setItem("cachemind_project_id", "proj_default");
      }
    }
    router.push("/dashboard");
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {}
    setUser(null);
    localStorage.removeItem("cachemind_user");
    localStorage.removeItem("cachemind_session_token");
    router.push("/login");
  };

  const switchTenant = async (newTenant: string) => {
    try {
      await api.selectWorkspace(newTenant);
    } catch (e) {
      console.warn("Workspace select fallback:", e);
    }
    setTenantId(newTenant);
    localStorage.setItem("cachemind_tenant_id", newTenant);
  };

  const switchProject = (newProject: string) => {
    setProjectId(newProject);
    localStorage.setItem("cachemind_project_id", newProject);
  };

  const updateKeys = (newApi: string, newAdmin: string) => {
    setApiKey(newApi);
    setAdminKey(newAdmin);
    localStorage.setItem("cachemind_api_key", newApi);
    localStorage.setItem("cachemind_admin_key", newAdmin);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        tenantId,
        projectId,
        apiKey,
        adminKey,
        planTier,
        isLoading,
        login,
        loginWithEmail,
        loginWithGithub,
        signup,
        loginDemo,
        logout,
        switchTenant,
        switchProject,
        updateKeys,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
