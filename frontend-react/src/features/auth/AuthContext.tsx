import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { supabase } from "../../config/supabaseClient";
import { apiRequest } from "../../lib/http";
import type { AuthResponse, SessionUser, UserType } from "../../types/auth";
import {
  clearStoredSession,
  getStoredToken,
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
  resendConfirmationEmail: (email: string) => Promise<void>;
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
        } else if (!getStoredToken()) {
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
      if (session?.access_token) {
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
      }

      const storedToken = getStoredToken();
      if (storedToken) {
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

      clearStoredSession();
      setUser(null);
      setToken(null);
      return null;
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

    // Supabase's password grant requires an email (not phone). If a phone
    // identifier is provided, instruct the user to use email or fallback to
    // the legacy app auth flow.
    if (!isEmail) {
      throw new Error(
        "Phone-based login is not supported with Supabase authentication. Please sign in using your email address."
      );
    }

    const loginPayload = { email: trimmed.toLowerCase(), password };

    let access_token: string | undefined;
    let userFromSupabase: any = null;

    try {
      const { data, error } = await supabase.auth.signInWithPassword(loginPayload as any);
      if (error) {
        throw error;
      }
      access_token = data.session?.access_token;
      userFromSupabase = data.user;
    } catch (supabaseError: any) {
      // "Email not confirmed" means this IS a Supabase-registered account,
      // just not verified yet -- falling through to the legacy backend
      // would just produce a confusing, unrelated error, since that
      // account doesn't exist there. Stop here with a clear message.
      const message = String(supabaseError?.message || "").toLowerCase();
      if (message.includes("email not confirmed") || message.includes("email_not_confirmed")) {
        throw new Error(
          "Please check your email and click the confirmation link before signing in. " +
          "Didn't get it? Check spam, or request a new confirmation email."
        );
      }

      // Any other Supabase auth failure (e.g. account genuinely predates
      // Supabase auth): fall back to the legacy backend JWT login so
      // existing app users are not locked out.
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

      access_token = data.access_token;
      const merged = normalizeUser(
        { ...(data.user || {}), role: data.user?.role },
        data.userType
      );

      if (!access_token || !merged) {
        throw new Error("Invalid login response");
      }

      const sessionType = merged.role === "super_admin" ? "superadmin" : (data.userType || "user");
      persistSession(access_token, merged, sessionType);
      setUser(merged);
      setToken(access_token);
      return merged;
    }

    if (!access_token) {
      if (userFromSupabase && !userFromSupabase.email_confirmed_at && !userFromSupabase.confirmed_at) {
        throw new Error("Please verify your email address before signing in.");
      }
      throw new Error("No access token received from Supabase");
    }

    localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
    setToken(access_token);

    const fetched = await apiRequest<SessionUser>("/auth/supabase/me");
    const userType: UserType = (fetched as any).user_type || "user";
    const isEmailVerified = Boolean(
      userFromSupabase?.email_confirmed_at || userFromSupabase?.confirmed_at
    );
    const merged = normalizeUser({ ...fetched, is_verified: isEmailVerified }, userType);
    if (merged) {
      persistSession(access_token, merged, userType);
    }
    setUser(merged);
    return merged!;
  }

  // SMS OTP flow (Supabase)
  async function sendSmsOtp(phone: string) {
    if (!supabase) throw new Error("Supabase is not configured");
    const trimmed = phone.trim();
    const { data, error } = await supabase.auth.signInWithOtp({ phone: trimmed });
    if (error) throw error;
    return data;
  }

  async function verifySmsOtp(phone: string, token: string) {
    if (!supabase) throw new Error("Supabase is not configured");
    const trimmed = phone.trim();
    const { data, error } = await supabase.auth.verifyOtp({ phone: trimmed, token, type: "sms" });
    if (error) throw error;

    const access_token = data.session?.access_token;
    if (!access_token) {
      throw new Error("No access token received after OTP verification");
    }

    localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
    setToken(access_token);

    const fetched = await apiRequest<SessionUser>("/auth/supabase/me");
    const userType: UserType = (fetched as any).user_type || "user";
    const merged = normalizeUser(fetched, userType);
    if (merged) {
      persistSession(access_token, merged, userType);
      setUser(merged);
    }
    return merged;
  }

  async function loginWithPhoneLegacy(phone: string, password: string) {
    const payload = { phone: phone.trim(), password };
    const data = await apiRequest<{ access_token?: string; user?: SessionUser; userType?: UserType }>(
      "/auth/login",
      { method: "POST", auth: false, body: payload }
    );

    const token = data.access_token;
    const merged = normalizeUser({ ...(data.user || {}), role: data.user?.role }, data.userType);

    if (!token || !merged) {
      throw new Error("Invalid login response from server");
    }

    const sessionType = merged.role === "super_admin" ? "superadmin" : (data.userType || "user");
    persistSession(token, merged, sessionType);
    setUser(merged);
    setToken(token);
    return merged;
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

    const isEmailVerified = Boolean(
      (signUpData.user as any).email_confirmed_at || (signUpData.user as any).confirmed_at
    );

    let session = signUpData.session;

    // With email confirmation OFF (the normal marketplace config), signUp
    // always returns a session. If it doesn't -- e.g. confirmation got
    // re-enabled, or a transient issue -- try an immediate sign-in before
    // giving up, so a real misconfiguration doesn't hard-block real users.
    if (!session) {
      const { data: signInData } = await supabase.auth.signInWithPassword({
        email: email.toLowerCase(),
        password,
      });
      session = signInData?.session ?? null;
    }

    if (!session?.access_token) {
      throw new Error(
        "Your account was created, but email confirmation is required before you can sign in. " +
        "Please check your inbox for a confirmation link."
      );
    }

    const access_token = session.access_token;
    localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
    setToken(access_token);

    const fetched = await apiRequest<SessionUser>("/auth/supabase/me");
    const fetchedType: UserType = (fetched as any).user_type || userType || "user";
    const merged = normalizeUser({ ...fetched, is_verified: isEmailVerified }, fetchedType);
    if (merged) {
      persistSession(access_token, merged, fetchedType);
      setUser(merged);
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
        token_hash: token,
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

  async function resendConfirmationEmail(email: string) {
    if (!supabase) {
      throw new Error("Email confirmation is not available for this account type.");
    }
    const { error } = await supabase.auth.resend({
      type: "signup",
      email: email.trim().toLowerCase(),
    });
    if (error) throw error;
  }

  return (
    <AuthContext.Provider
      value={{ user, token, loading, login, register, logout, refreshUser, verifyEmail, resendConfirmationEmail }}
    >
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