import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { apiRequest } from "../../lib/http";
import type { AuthResponse, SessionUser, UserType } from "../../types/auth";
import {
  clearStoredSession,
  getStoredUser,
  getStoredUserType,
  normalizeUser,
  persistSession,
  ACCESS_TOKEN_KEY,
} from "./authStorage";

interface RegisterPayload {
  name: string;
  email: string;
  password: string;
}

interface AuthContextValue {
  user: SessionUser | null;
  token: string | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<SessionUser>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<SessionUser | null>;
  verifyEmail: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(getStoredUser());
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refreshUser();
  }, []);

  async function refreshUser() {
    try {
      const response = await apiRequest<{ access_token: string }>("/auth/refresh", {
        method: "POST",
        auth: false,
      });
      // On successful refresh, fetch user data
      const userType = getStoredUserType();
      const endpoint =
        userType === "business"
          ? "/business/me"
          : userType === "logistics"
            ? "/logistics/me"
            : userType === "superadmin"
              ? "/auth/me"
              : "/auth/me";
      const fallbackType = userType || "user";
      const fetched = await apiRequest<SessionUser>(endpoint);
      const next = normalizeUser(fetched, fallbackType);
      if (next) {
        // Only persist user data, tokens are in cookies
        persistSession(response.access_token, next, userType);
      }
      setUser(next);
      setToken(response.access_token);
      return next;
    } catch (err) {
      clearStoredSession();
      setUser(null);
      setToken(null);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function login(identifier: string, password: string) {
    const trimmed = identifier.trim();
    const isEmail = trimmed.includes("@");

    const payload = isEmail
      ? { email: trimmed.toLowerCase(), password }
      : { phone: trimmed, password };

    const data = await apiRequest<AuthResponse & { access_token?: string }>("/auth/login", {
      method: "POST",
      auth: false,
      body: payload,
    });

    const token = data.access_token;
    const merged = normalizeUser({ ...(data.user || {}), role: data.user?.role }, data.userType);

    if (!token || !merged) {
      throw new Error("Invalid login response");
    }

    const sessionType = merged.role === "super_admin" ? "superadmin" : (data.userType || "user");
    persistSession(token, merged, sessionType);
    setUser(merged);
    setToken(token);
    return merged;
  }

  async function register(payload: RegisterPayload) {
    const data = await apiRequest<{ access_token?: string; user?: SessionUser; userType?: UserType }>("/auth/register", {
      method: "POST",
      auth: false,
      body: payload,
    });

    const token = data.access_token;
    const merged = normalizeUser({ ...(data.user || {}), role: data.user?.role }, data.userType);

    if (!token || !merged) {
      throw new Error("Invalid registration response");
    }

    const sessionType = merged.role === "super_admin" ? "superadmin" : (data.userType || "user");
    persistSession(token, merged, sessionType);
    setUser(merged);
    setToken(token);
  }

  async function logout() {
    await apiRequest("/auth/logout", {
      method: "POST",
      auth: false,
    });
    clearStoredSession();
    setUser(null);
    setToken(null);
  }
  
  async function verifyEmail(token: string) {
    await apiRequest("/auth/verify-email", {
      method: "POST",
      auth: false,
      body: { token },
    });
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUser, verifyEmail }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

