import { env } from "../config/env";
import { clearStoredSession, getStoredToken } from "../features/auth/authStorage";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions extends Omit<RequestInit, "body" | "method"> {
  method?: HttpMethod;
  body?: unknown;
  auth?: boolean;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const method = options.method || "GET";

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${env.apiBase}${path}`, {
    ...options,
    method,
    headers,
    body: serializeBody(options.body),
    credentials: "include", // Ensure cookies are sent with requests
    cache: options.cache ?? (method === "GET" ? "no-store" : options.cache),
  });

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
