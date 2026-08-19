Local development: frontend, backend, and database

Ports and services

- Frontend (Vite dev): http://localhost:5173 (default when running `cd frontend-react && npm run dev`)
- Frontend (Docker preview / compose): http://localhost:8080 (docker-compose maps 8080 → container)
- Backend (Uvicorn): http://localhost:8000 (default when running `uvicorn backend.app.main:app --reload --port 8000`)
- Postgres (docker-compose): port 5432 → host 5432

Environment variables

- Use the repo root `.env` for hosted defaults (points to Supabase DB). For local dev with docker-compose the backend service uses `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` from the compose file.
- Frontend `.env` (frontend-react/.env) sets `VITE_API_BASE` for local dev. When using docker-compose the frontend container is configured to use `http://backend:8000` so it reaches the backend service internally.

Key harmonization points

- Backend DB selection: `backend/database.py` will prefer `DATABASE_URL` if present, otherwise it constructs a URL from `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`/`DB_PORT`. Running locally with docker-compose uses the DB_* variables so the backend connects to the `db` service.
- When running frontend in a browser (either Vite dev or docker-preview), the browser-origin must be permitted in `CORS_ORIGINS`. The backend reads `CORS_ORIGINS` from environment and configures `CORSMiddleware` accordingly.

Docker-compose tips

- Start everything together (builds + services):

```bash
# from repo root
docker-compose up --build
```

- Access frontend at `http://localhost:8080` (if using docker-compose) or `http://localhost:5173` (if using Vite dev). The frontend will use `env.apiBase` to call the backend.

Debugging CORS / auth issues

- If you see CORS errors in the browser console, check the `Access-Control-Allow-Origin` response header for the API call (Network tab). It must match the page origin and the backend must set `Access-Control-Allow-Credentials: true` if cookies are used.
- Avoid `CORS_ORIGINS` containing `*` when `allow_credentials=True` — browsers will block Set-Cookie in that case.
- For cookie auth across origins, ensure `Set-Cookie` includes `SameSite=None; Secure` when using HTTPS.

If you want, I can:
- Run the stack locally here and show the network headers and any CORS errors, or
- Update other hosted configs (Netlify/GitHub Actions) to ensure `VITE_API_BASE` and `CORS_ORIGINS` are consistent.
