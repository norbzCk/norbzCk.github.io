Hosted deployment checklist

What I changed

- Updated `render.yaml` to set `CORS_ORIGINS` to explicit origins (no wildcard):
  - `https://norbzCk.github.io`
  - `https://sokolink-frontend.onrender.com` (Render frontend service)
  - `http://localhost:5173`, `http://localhost:3000` (local dev)

Why redeploy

- Render reads `render.yaml` at deploy time. After pushing `render.yaml` you must redeploy the `sales-backend` service (or re-trigger a build) so the environment variable `CORS_ORIGINS` on the running service includes the new values. Without redeploy the running service may still use the old `CORS_ORIGINS`.

Steps to validate after redeploy

1. Visit the frontend site (GitHub Pages, Render static site, or Netlify). Open browser DevTools → Network. Make an API request (page action). Verify the API response includes `Access-Control-Allow-Origin` matching the frontend origin and `Access-Control-Allow-Credentials: true` if you rely on cookies.

2. Test backend health endpoint:

```bash
curl -i https://<your-backend-host>/healthz
```

Expect `200 OK` and JSON `{"status": "ok", "database": "connected"}`.

3. If you use GitHub Actions to build the frontend (Pages), ensure the secret `VITE_API_BASE` is set to your backend base URL in repository Settings → Secrets so the built frontend calls the correct API.

4. If you use Netlify or Render for the static frontend, ensure the environment variable `VITE_API_BASE` points to the backend URL returned by your host.

Notes and troubleshooting

- Do NOT include `*` in `CORS_ORIGINS` while `allow_credentials=True` — browsers will block Set-Cookie in that case.
- If your frontend and backend are on different origins and you use cookie auth, ensure cookies use `SameSite=None; Secure` and your HTTPS setup is correct.

If you want I can:
- Re-run a hosted validation by making requests to your deployed backend and reporting headers (needs a public URL), or
- Update your GitHub Actions / Netlify environment var files to ensure `VITE_API_BASE` is set correctly.
