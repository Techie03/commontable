// Auth context: login / register / logout, current user + roles.
// Tokens live in localStorage and are attached by lib/api.ts.
// All storage access happens in effects or event handlers so server-side
// prerendering never touches window or localStorage.

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearAuthStorage,
  fetchMe,
  getAccessToken,
  getStoredUser,
  login as apiLogin,
  logoutRequest,
  register as apiRegister,
  storeTokens,
  storeUser,
} from "./api";
import {
  hasAnyRole,
  normalizeRoles,
  restaurantScopeId,
  type Role,
  type RoleAssignment,
  type User,
} from "./types";

interface AuthContextValue {
  user: User | null;
  /** True once the initial stored session check has finished. */
  ready: boolean;
  /** True while a login/register request is in flight. */
  busy: boolean;
  roles: RoleAssignment[];
  hasRole: (...roles: Role[]) => boolean;
  /** Restaurant id this user is scoped to, for restaurant roles. */
  restaurantId: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName: string,
    role?: string
  ) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);

  // Restore a stored session on first render (client only).
  useEffect(() => {
    let cancelled = false;
    const stored = getStoredUser();
    if (stored) setUser(stored);
    if (!getAccessToken()) {
      setReady(true);
      return () => {
        cancelled = true;
      };
    }
    fetchMe()
      .then((fresh) => {
        if (cancelled) return;
        setUser(fresh);
        storeUser(fresh);
      })
      .catch(() => {
        // Offline or expired session: keep the stored user for display,
        // but the next API call will surface the real state. If the token
        // was cleared by a failed refresh, drop the stored user too.
        if (!getAccessToken()) {
          setUser(null);
          clearAuthStorage();
        }
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setBusy(true);
    try {
      const res = await apiLogin(email, password);
      storeTokens(res.access_token, res.refresh_token);
      storeUser(res.user);
      setUser(res.user);
    } finally {
      setBusy(false);
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName: string, role?: string) => {
      setBusy(true);
      try {
        const res = await apiRegister(email, password, fullName, role ?? "customer");
        storeTokens(res.access_token, res.refresh_token);
        storeUser(res.user);
        setUser(res.user);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const logout = useCallback(() => {
    // Best effort server side revocation; local sign out always happens.
    logoutRequest().catch(() => undefined);
    clearAuthStorage();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const fresh = await fetchMe();
    storeUser(fresh);
    setUser(fresh);
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const roles = normalizeRoles(user);
    return {
      user,
      ready,
      busy,
      roles,
      hasRole: (...wanted: Role[]) => hasAnyRole(user, wanted),
      restaurantId: restaurantScopeId(user),
      login,
      register,
      logout,
      refreshUser,
    };
  }, [user, ready, busy, login, register, logout, refreshUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}

/** Default landing page for a user, based on their roles. */
export function homeForUser(user: User | null): string {
  if (!user) return "/order";
  if (hasAnyRole(user, ["admin"])) return "/admin";
  if (hasAnyRole(user, ["dispatcher"])) return "/dispatch";
  if (hasAnyRole(user, ["driver"])) return "/driver";
  if (
    hasAnyRole(user, [
      "restaurant_owner",
      "restaurant_manager",
      "restaurant_staff",
    ])
  ) {
    return "/restaurant";
  }
  return "/order";
}
