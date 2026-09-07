import { env } from "../config/env";
import { clearStoredSession, getStoredToken } from "../features/auth/authStorage";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions extends Omit<RequestInit, "body" | "method"> {
  method?: HttpMethod;
  body?: unknown;
  auth?: boolean;
  /** Milliseconds before the request is aborted. Default 30s. Render's free
   * tier can take 30-60s to wake a sleeping service on the first request
   * after inactivity -- this is generous enough to survive that, while
   * still guaranteeing the UI never hangs forever with no feedback. */
  timeoutMs?: number;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export class ApiTimeoutError extends Error {
  constructor(path: string, timeoutMs: number) {
    super(
      `Request to ${path} timed out after ${Math.round(timeoutMs / 1000)}s. ` +
        `If this is a freshly-deployed backend on Render's free tier, it may still be waking up -- try again in a moment. ` +
        `Otherwise, check that the app is pointed at the right backend URL.`,
    );
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const method = options.method || "GET";
  const timeoutMs = options.timeoutMs ?? 30000;

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // Send the stored access token (Supabase JWT or app JWT) as a Bearer header
  if (options.auth !== false) {
    const token = getStoredToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${env.apiBase}${path}`, {
      ...options,
      method,
      headers,
      body: serializeBody(options.body),
      credentials: "include", // Send cookies (for backward-compat with app JWT flow)
      cache: options.cache ?? (method === "GET" ? "no-store" : options.cache),
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      // A request that never resolves (wrong backend URL, sleeping Render
      // service, network black hole) used to hang the UI forever with no
      // feedback at all -- this turns that into a clear, catchable error.
      throw new ApiTimeoutError(path, timeoutMs);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function serializeBody(body: unknown): BodyInit | null | undefined {
  if (body == null) return undefined;
  if (body instanceof FormData) return body;
  if (typeof body === "string") return body;
  return JSON.stringify(body);
}

async function readErrorMessage(response: Response) {
  try {
    const data = await response.json();
    return data.detail || data.message || "Request failed";
  } catch {
    return response.statusText || "Request failed";
  }
}

