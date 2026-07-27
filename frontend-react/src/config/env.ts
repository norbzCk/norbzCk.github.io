function resolveDefaultApiBase() {
  if (typeof window === "undefined") {
    return "http://localhost:8000";
  }

  const { hostname, origin, protocol } = window.location;

  // Local development — talk directly to the FastAPI backend on port 8000
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:8000";
  }

  // On a custom domain or deployed frontend — use the same origin
  // so the API is served from the same host as the frontend
  if (protocol === "https:") {
    return origin.replace(/\/+$/, "");
  }

  return origin.replace(/\/+$/, "");
}

export const env = {
  apiBase: (import.meta.env.VITE_API_BASE || resolveDefaultApiBase()).replace(/\/+$/, ""),
};
