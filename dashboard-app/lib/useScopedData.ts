"use client";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
/** Discard late responses after scope changes; never render another scope's cached view. */
export function useScopedData<T>(loader: (tenant: string, project?: string) => Promise<T>, refresh = 0) {
  const { activeWorkspace, activeProject } = useAuth();
  const scope = `${activeWorkspace?.id ?? ""}/${activeProject?.id ?? ""}`;
  const current = useRef(scope); current.current = scope;
  const [state, setState] = useState<{ scope: string; data: T | null; error: string; loading: boolean }>({ scope, data: null, error: "", loading: true });
  useEffect(() => {
    let cancelled = false;
    setState({ scope, data: null, error: "", loading: true });
    if (!activeWorkspace?.id) { setState({ scope, data: null, error: "Select a workspace to load data.", loading: false }); return; }
    loader(activeWorkspace.id, activeProject?.id).then(data => {
      if (!cancelled && current.current === scope) setState({ scope, data, error: "", loading: false });
    }).catch(error => {
      if (!cancelled && current.current === scope) setState({ scope, data: null, error: error instanceof Error ? error.message : "Unable to load data.", loading: false });
    });
    return () => { cancelled = true; };
  }, [scope, activeWorkspace?.id, activeProject?.id, loader, refresh]);
  return state.scope === scope ? state : { scope, data: null, error: "", loading: true };
}
