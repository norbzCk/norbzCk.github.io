import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    build: {
        crossorigin: "anonymous",
    },
    server: {
        port: 5173,
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
        },
    },
});
