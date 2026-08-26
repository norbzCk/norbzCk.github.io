function resolveDefaultApiBase() {
  if (typeof window === "undefined") {
    return "http://localhost:8000";
  }

  const { hostname, origin, protocol } = window.location;

  // Local development — talk directly to the FastAPI backend on port 8000
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:8000";
  }

  // GitHub Pages — API falls back to Render backend
  if (hostname.endsWith("github.io")) {
    return "https://sales-backend.onrender.com";
  }

  // Railway — API on the same Railway app
  if (hostname.endsWith("railway.app")) {
    return "https://sales-analysis-api-production.up.railway.app/";
  }

  // On a custom domain or deployed frontend — use the same origin
  // so the API is served from the same host as the frontend
  if (protocol === "https:") {
    return origin.replace(/\/+$/, "");
  }

  return origin.replace(/\/+$/, "");
}

function resolveDefaultAgentApiBase() {
  if (typeof window === "undefined") {
    return "http://localhost:8001";
  }

  const { hostname } = window.location;

  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:8001";
  }

  // Deployed — the standalone agent service on Render
  return "https://sokolink-agent.onrender.com";
}

export const env = {
  apiBase: (import.meta.env.VITE_API_BASE || resolveDefaultApiBase()).replace(/\/+$/, ""),
  agentApiBase: (import.meta.env.VITE_AGENT_API_BASE || resolveDefaultAgentApiBase()).replace(/\/+$/, ""),
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL || "",
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY || "",
};
