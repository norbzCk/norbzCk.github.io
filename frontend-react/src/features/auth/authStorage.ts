import type { SessionUser, UserType } from "../../types/auth";

export const ACCESS_TOKEN_KEY = "access_token";
const SESSION_USER_KEY = "session_user";
const USER_TYPE_KEY = "user_type";
const USER_ROLE_KEY = "user_role";

export function normalizeRole(value?: string) {
  const role = String(value || "").trim().toLowerCase();
  if (role === "customer") return "user";
  if (role === "business") return "seller";
  return role;
}

export function normalizeUser(user?: SessionUser | null, fallbackType: UserType = ""): SessionUser | null {
  if (!user) return null;
  const next = { ...user };
  if (!next.role && fallbackType) {
    next.role = fallbackType === "business" ? "seller" : fallbackType;
  }
  if (next.role) next.role = normalizeRole(next.role);
  return next;
}

export function getStoredUser() {
  const raw = localStorage.getItem(SESSION_USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function getStoredUserType() {
  return (localStorage.getItem(USER_TYPE_KEY) || "") as UserType;
}

export function persistSession(token: string, user: SessionUser, userType: UserType = "") {
  const normalized = normalizeUser(user, userType);
  // Access token and refresh token will now be handled by HTTP-only cookies from the backend.
  // This function is now only responsible for persisting user data if needed for UI, not tokens.
  localStorage.setItem(SESSION_USER_KEY, JSON.stringify(normalized || {}));
  if (userType) {
    localStorage.setItem(USER_TYPE_KEY, userType);
  }
  if (normalized?.role) {
    localStorage.setItem(USER_ROLE_KEY, String(normalized.role));
  }
}

export function clearStoredSession() {
  // Access token and refresh token are cleared by the backend when logging out via API call.
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(SESSION_USER_KEY);
  localStorage.removeItem(USER_TYPE_KEY);
  localStorage.removeItem(USER_ROLE_KEY);
  localStorage.removeItem("business_user");
  localStorage.removeItem("logistics_user");
}

export function getStoredToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function hasAdminAccess(role?: string) {
  return ["admin", "super_admin", "owner"].includes(normalizeRole(role));
}

export function hasSuperadminAccess(role?: string) {
  return normalizeRole(role) === "super_admin";
}

export function getPostLoginPath(user?: SessionUser | null) {
  const userType = getStoredUserType().toLowerCase();
  const role = normalizeRole(String(user?.role || ""));
  if (userType === "superadmin" || role === "super_admin" || role === "owner") return "/app/superadmin";
  if (userType === "logistics" || role === "logistics") return "/app/logistics";
  if (userType === "business" || role === "seller") return "/app/seller";
  if (hasAdminAccess(role)) return "/app/dashboard";
  return "/app/customer";
}
