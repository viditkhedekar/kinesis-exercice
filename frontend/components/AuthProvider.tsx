"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RegisterResult, ResendResult, User, UserPrefs } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<User>;
  // Registration does NOT log in — the account must be verified by email first.
  register: (email: string, name: string, password: string) => Promise<RegisterResult>;
  verifyEmail: (token: string) => Promise<User>;
  resendVerification: (email: string) => Promise<ResendResult>;
  logout: () => Promise<void>;
  updatePrefs: (patch: { name?: string; prefs?: UserPrefs }) => Promise<User>;
  refresh: () => Promise<void>;
}

const AuthCtx = createContext<AuthState>(null as unknown as AuthState);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const u = await api.login(email, password, remember);
    setUser(u);
    return u;
  }, []);

  const register = useCallback(async (email: string, name: string, password: string) => {
    // Returns a "check your inbox" result; the user isn't authenticated yet.
    return api.register(email, name, password);
  }, []);

  const verifyEmail = useCallback(async (token: string) => {
    const u = await api.verifyEmail(token);
    setUser(u); // verifying logs the user in (cookie set by the backend)
    return u;
  }, []);

  const resendVerification = useCallback((email: string) => api.resendVerification(email), []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  const updatePrefs = useCallback(async (patch: { name?: string; prefs?: UserPrefs }) => {
    const u = await api.updateMe(patch);
    setUser(u);
    return u;
  }, []);

  return (
    <AuthCtx.Provider value={{ user, loading, login, register, verifyEmail, resendVerification, logout, updatePrefs, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
