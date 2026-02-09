"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import {
  type AuthUser,
  type AuthTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  isAuthenticated as checkAuth,
  isTokenExpired,
} from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_V1 = `${API_BASE}/api/v1`;

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async (token: string): Promise<AuthUser | null> => {
    try {
      const res = await fetch(`${API_V1}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }, []);

  const refreshAuth = useCallback(async (): Promise<boolean> => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${API_V1}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        clearTokens();
        setUser(null);
        return false;
      }

      const tokens: AuthTokens = await res.json();
      setTokens(tokens);

      const userData = await fetchUser(tokens.access_token);
      if (userData) {
        setUser(userData);
        return true;
      }

      clearTokens();
      setUser(null);
      return false;
    } catch {
      clearTokens();
      setUser(null);
      return false;
    }
  }, [fetchUser]);

  // Initialize auth state on mount
  useEffect(() => {
    async function init() {
      if (!checkAuth()) {
        setIsLoading(false);
        return;
      }

      const accessToken = getAccessToken()!;

      // If access token expired, try refresh
      if (isTokenExpired(accessToken)) {
        await refreshAuth();
        setIsLoading(false);
        return;
      }

      // Validate with /me endpoint
      const userData = await fetchUser(accessToken);
      if (userData) {
        setUser(userData);
      } else {
        // Token invalid, try refresh
        await refreshAuth();
      }
      setIsLoading(false);
    }
    init();
  }, [fetchUser, refreshAuth]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_V1}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.detail || "Неверный email или пароль");
    }

    const tokens: AuthTokens = await res.json();
    setTokens(tokens);

    const userData = await fetchUser(tokens.access_token);
    setUser(userData);
  }, [fetchUser]);

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const res = await fetch(`${API_V1}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.detail || "Ошибка регистрации");
    }

    const tokens: AuthTokens = await res.json();
    setTokens(tokens);

    const userData = await fetchUser(tokens.access_token);
    setUser(userData);
  }, [fetchUser]);

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await fetch(`${API_V1}/auth/logout`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // Logout is best-effort
      }
    }
    clearTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
