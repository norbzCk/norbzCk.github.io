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

  // Deployed frontend with no VITE_API_BASE set: falling back to "same
  // origin as the frontend" is only correct if the backend is literally
  // served from that same host. If frontend and backend are two SEPARATE
  // Render services (two different *.onrender.com URLs, a common setup),
  // this guess is wrong -- every API call silently goes to the frontend's
  // own URL instead of the real backend, which has no matching route
  // there. Depending on the static-site config that can 404 quickly, or
  // get swallowed by an SPA catch-all rewrite and hang/confuse the caller.
  // Loud and clear on purpose: this is exactly the kind of misconfiguration
  // that otherwise looks like "the app is just stuck" with zero clue why.
  if (hostname.endsWith("onrender.com") && !import.meta.env.VITE_API_BASE) {
    // eslint-disable-next-line no-console
    console.error(
      "[SokoLnk] VITE_API_BASE is not set. Falling back to this same origin " +
        `(${origin}) for API calls, which is WRONG if your backend is a ` +
        "separate Render service. Go to your frontend service on Render -> " +
        "Environment -> add VITE_API_BASE=<your backend's Render URL>, then " +
        "redeploy. Until that's set, requests to a separate backend service " +
        "will fail or hang.",
    );
  }

  // On a custom domain or deployed frontend — use the same origin
  // so the API is served from the same host as the frontend
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
