import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    build: {
        crossorigin: "anonymous",
    },
    server: {
        port: 5173,
        // NOTE: frontend-react/src/config/env.ts currently always resolves
        // apiBase to an ABSOLUTE URL (http://localhost:8000) on localhost, so
        // every API call is a real cross-origin request and this proxy is
        // NOT actually engaged in the current setup -- CORS on the backend
        // (backend/app/main.py) is what makes local dev work, not this list.
        // Kept complete and accurate anyway in case that ever changes, so it
        // doesn't silently 404 whichever router someone forgot to add.
        proxy: {
            "/auth": "http://127.0.0.1:8000",
            "/business": "http://127.0.0.1:8000",
            "/logistics": "http://127.0.0.1:8000",
            "/products": "http://127.0.0.1:8000",
            "/orders": "http://127.0.0.1:8000",
            "/payments": "http://127.0.0.1:8000",
            "/providers": "http://127.0.0.1:8000",
            "/customers": "http://127.0.0.1:8000",
            "/sales": "http://127.0.0.1:8000",
            "/rfq": "http://127.0.0.1:8000",
            "/dashboard": "http://127.0.0.1:8000",
            "/superadmin": "http://127.0.0.1:8000",
            "/uploads": "http://127.0.0.1:8000",
            "/ai": "http://127.0.0.1:8000",
            "/notifications": "http://127.0.0.1:8000",
            "/disputes": "http://127.0.0.1:8000",
        },
    },
});
