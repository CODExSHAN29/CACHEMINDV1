"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";

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
    try {
      const storedUser = localStorage.getItem("cachemind_user");
      const storedTenant = localStorage.getItem("cachemind_tenant_id");
      const storedProject = localStorage.getItem("cachemind_project_id");
      const storedApiKey = localStorage.getItem("cachemind_api_key");
      const storedAdminKey = localStorage.getItem("cachemind_admin_key");
      const storedTier = localStorage.getItem("cachemind_tier") as any;

      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }

      if (storedTenant) setTenantId(storedTenant);
      if (storedProject) setProjectId(storedProject);
      if (storedApiKey) setApiKey(storedApiKey);
      if (storedAdminKey) setAdminKey(storedAdminKey);
      if (storedTier) setPlanTier(storedTier);
    } catch (e) {
      console.warn("Auth initialization fallback:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loginWithEmail = async (email: string, pass: string): Promise<boolean> => {
    const rawName = email.split("@")[0] || "Developer";
    const formattedName = rawName.charAt(0).toUpperCase() + rawName.slice(1);
    const domain = email.split("@")[1]?.split(".")[0] || "org";
    const orgName = domain.charAt(0).toUpperCase() + domain.slice(1) + " Corp";
    const tenantSlug = `tenant_${domain.toLowerCase()}`;

    const newUser: User = {
      id: "usr_" + Math.random().toString(36).substring(2, 9),
      name: formattedName,
      email,
      organization: orgName,
      role: "admin",
      provider: "email",
    };

    setUser(newUser);
    setTenantId(tenantSlug);
    localStorage.setItem("cachemind_user", JSON.stringify(newUser));
    localStorage.setItem("cachemind_tenant_id", tenantSlug);
    localStorage.setItem("cachemind_api_key", DEFAULT_DEV_KEY);
    localStorage.setItem("cachemind_admin_key", DEFAULT_ADMIN_KEY);
    return true;
  };

  const login = async (email: string, pass: string, tenant = "tenant_default"): Promise<boolean> => {
    return loginWithEmail(email, pass);
  };

  const loginWithGithub = async (githubHandle = "octocat-engineer"): Promise<boolean> => {
    const cleanHandle = githubHandle.trim() || "github-developer";
    const newUser: User = {
      id: "usr_gh_" + Math.random().toString(36).substring(2, 9),
      name: cleanHandle,
      email: `${cleanHandle.toLowerCase()}@users.noreply.github.com`,
      organization: `${cleanHandle}'s Workspace`,
      role: "admin",
      avatarUrl: `https://github.com/${cleanHandle}.png`,
      provider: "github",
    };

    const tenantSlug = `tenant_${cleanHandle.toLowerCase().replace(/[^a-z0-9]/g, "_")}`;

    setUser(newUser);
    setTenantId(tenantSlug);
    setApiKey(DEFAULT_DEV_KEY);
    setAdminKey(DEFAULT_ADMIN_KEY);
    setPlanTier("growth");

    localStorage.setItem("cachemind_user", JSON.stringify(newUser));
    localStorage.setItem("cachemind_tenant_id", tenantSlug);
    localStorage.setItem("cachemind_api_key", DEFAULT_DEV_KEY);
    localStorage.setItem("cachemind_admin_key", DEFAULT_ADMIN_KEY);
    localStorage.setItem("cachemind_tier", "growth");
    return true;
  };

  const signup = async (
    name: string,
    email: string,
    pass: string,
    org: string,
    tier: "developer" | "growth" | "enterprise" = "growth"
  ): Promise<boolean> => {
    const slug = org.toLowerCase().replace(/[^a-z0-9]/g, "_") || "tenant_custom";
    const newUser: User = {
      id: "usr_" + Math.random().toString(36).substring(2, 9),
      name,
      email,
      organization: org,
      role: "admin",
      provider: "email",
    };
    setUser(newUser);
    setTenantId(slug);
    setPlanTier(tier);
    localStorage.setItem("cachemind_user", JSON.stringify(newUser));
    localStorage.setItem("cachemind_tenant_id", slug);
    localStorage.setItem("cachemind_tier", tier);
    localStorage.setItem("cachemind_api_key", DEFAULT_DEV_KEY);
    localStorage.setItem("cachemind_admin_key", DEFAULT_ADMIN_KEY);
    return true;
  };

  const loginDemo = () => {
    const demoUser: User = {
      id: "usr_developer_demo",
      name: "Demo Developer",
      email: "demo@cachemind.ai",
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
    localStorage.setItem("cachemind_api_key", DEFAULT_DEV_KEY);
    localStorage.setItem("cachemind_admin_key", DEFAULT_ADMIN_KEY);
    localStorage.setItem("cachemind_tier", "growth");

    router.push("/dashboard");
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("cachemind_user");
    router.push("/login");
  };

  const switchTenant = (newTenant: string) => {
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
