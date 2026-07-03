"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { User, UserPrefs } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<User>;
  register: (email: string, name: string, password: string) => Promise<User>;
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
    const u = await api.register(email, name, password);
    setUser(u);
    return u;
  }, []);

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
    <AuthCtx.Provider value={{ user, loading, login, register, logout, updatePrefs, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
