import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { supabase } from "../../config/supabaseClient";
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
  phone?: string;
  userType?: UserType;
}

interface AuthContextValue {
  user: SessionUser | null;
  token: string | null;
  loading: boolean;
  login: (identifier: string, password: string, userType?: UserType) => Promise<SessionUser>;
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

    // Listen for Supabase auth state changes (token refresh, sign-out, etc.)
    if (supabase) {
      const { data: listener } = supabase.auth.onAuthStateChange(async (_event, session) => {
        if (session?.access_token) {
          localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
          setToken(session.access_token);
          const fetched = await apiRequest<SessionUser>("/auth/supabase/me", { auth: true });
          const storedType = getStoredUserType();
          const next = normalizeUser(fetched, storedType || (fetched as any).user_type || "user");
          if (next) {
            persistSession(session.access_token, next, storedType || "user");
          }
          setUser(next);
        } else {
          clearStoredSession();
          setUser(null);
          setToken(null);
        }
      });
      return () => {
        listener?.subscription.unsubscribe();
      };
    }
  }, []);

  async function refreshUser() {
    try {
      if (!supabase) {
        // Fallback: try app JWT refresh (backward compat)
        const response = await apiRequest<{ access_token: string }>("/auth/refresh", {
          method: "POST",
          auth: false,
        });
        const userType = getStoredUserType();
        const endpoint =
          userType === "business"
            ? "/business/me"
            : userType === "logistics"
              ? "/logistics/me"
              : "/auth/me";
        const fallbackType = userType || "user";
        const fetched = await apiRequest<SessionUser>(endpoint);
        const next = normalizeUser(fetched, fallbackType);
        if (next) {
          persistSession(response.access_token, next, userType);
        }
        setUser(next);
        setToken(response.access_token);
        return next;
      }

      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        clearStoredSession();
        setUser(null);
        setToken(null);
        return null;
      }

      localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
      setToken(session.access_token);

      const fetched = await apiRequest<SessionUser>("/auth/supabase/me", {
        auth: true,
      });
      const storedType = getStoredUserType();
      const userType: UserType = (fetched as any).user_type || storedType || "user";
      const next = normalizeUser(fetched, userType);
      if (next) {
        persistSession(session.access_token, next, userType);
      }
      setUser(next);
      return next;
    } catch (_err) {
      clearStoredSession();
      setUser(null);
      setToken(null);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function login(identifier: string, password: string, _userType?: UserType) {
    if (!supabase) {
      // Fallback: old app JWT login
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
      const merged = normalizeUser(
        { ...(data.user || {}), role: data.user?.role },
        data.userType
      );

      if (!token || !merged) {
        throw new Error("Invalid login response");
      }

      const sessionType = merged.role === "super_admin" ? "superadmin" : (data.userType || "user");
      persistSession(token, merged, sessionType);
      setUser(merged);
      setToken(token);
      return merged;
    }

    const trimmed = identifier.trim();
    const isEmail = trimmed.includes("@");
    const loginPayload: { email?: string; phone?: string; password: string } = { password };

    if (isEmail) {
      loginPayload.email = trimmed.toLowerCase();
    } else {
      loginPayload.phone = trimmed;
    }

    const { data, error } = await supabase.auth.signInWithPassword(loginPayload);

    if (error) {
      throw error;
    }

    const access_token = data.session?.access_token;
    if (!access_token) {
      // Might need email verification — Supabase returns user but no session
      if (data.user && !data.session) {
        throw new Error("Please verify your email address before signing in.");
      }
      throw new Error("No access token received from Supabase");
    }

    localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
    setToken(access_token);

    const fetched = await apiRequest<SessionUser>("/auth/supabase/me");
    const userType: UserType = (fetched as any).user_type || "user";
    const merged = normalizeUser(fetched, userType);
    if (merged) {
      persistSession(access_token, merged, userType);
    }
    setUser(merged);
    return merged!;
  }

  async function register(payload: RegisterPayload) {
    const { name, email, password, phone, userType } = payload;

    if (!supabase) {
      const appPayload: Record<string, unknown> = { name, email, password };
      if (phone) appPayload.phone = phone;

      const data = await apiRequest<{ access_token?: string; user?: SessionUser; userType?: UserType }>(
        "/auth/register",
        { method: "POST", auth: false, body: appPayload }
      );

      const token = data.access_token;
      const merged = normalizeUser({ ...(data.user || {}), role: data.user?.role }, data.userType);

      if (!token || !merged) {
        throw new Error("Invalid registration response");
      }

      const sessionType = merged.role === "super_admin" ? "superadmin" : (data.userType || "user");
      persistSession(token, merged, sessionType);
      setUser(merged);
      setToken(token);
      return;
    }

    const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
      email: email.toLowerCase(),
      password,
      options: {
        data: {
          name,
          ...(phone ? { phone } : {}),
          user_type: userType || "user",
          ...(userType === "business" ? { business_name: name } : {}),
        },
      },
    });

    if (signUpError) {
      throw signUpError;
    }

    if (!signUpData.user) {
      throw new Error("Supabase sign-up failed");
    }

    // If email confirmations are enabled, the user will get an email to confirm
    if (!signUpData.session) {
      // No session yet (email confirmation required) — still persist what we can
      if (signUpData.user.email_confirm_at === null || signUpData.user.confirmed_at === null) {
        throw new Error("Please check your email to confirm your account before signing in.");
      }
    }

    const access_token = signUpData.session?.access_token;

    if (access_token) {
      localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
      setToken(access_token);

      const fetched = await apiRequest<SessionUser>("/auth/supabase/me");
      const fetchedType: UserType = (fetched as any).user_type || userType || "user";
      const merged = normalizeUser(fetched, fetchedType);
      if (merged) {
        persistSession(access_token, merged, fetchedType);
        setUser(merged);
      }
    } else {
      const user_obj: SessionUser = {
        id: signUpData.user.id,
        name,
        email: signUpData.user.email,
        phone: phone || signUpData.user.phone,
        role: userType === "business" ? "seller" : userType === "logistics" ? "logistics" : "user",
      };
      persistSession(signUpData.user.id as unknown as string, user_obj, userType || "user");
      setUser(user_obj);
    }
  }

  async function logout() {
    if (supabase) {
      await supabase.auth.signOut();
    } else {
      await apiRequest("/auth/logout", {
        method: "POST",
        auth: false,
      });
    }
    clearStoredSession();
    setUser(null);
    setToken(null);
  }

  async function verifyEmail(token: string) {
    if (supabase) {
      const { error } = await supabase.auth.verifyOtp({
        token,
        type: "email",
      });
      if (error) throw error;
    } else {
      await apiRequest("/auth/verify-email", {
        method: "POST",
        auth: false,
        body: { token },
      });
    }
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