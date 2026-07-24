# Sales Dashboard Web Application

A full-stack sales analytics dashboard that visualizes revenue, orders, units sold, and product performance using a FastAPI backend. The repository now contains both the original lightweight HTML/CSS/JavaScript frontend and a new React + TypeScript frontend architecture for incremental migration.

## Features

## Real-time sales statistics

Total revenue

Total orders

Units sold

Top-selling product

## Interactive charts

Revenue by product (Bar Chart)

Revenue over time (Line Chart)

## FastAPI REST API

#SQLAlchemy ORM for database access

# Clean and a responsive dashboard UI

## Tech Stack
# Backend

Python

FastAPI

SQLAlchemy

PostgreSQL

Uvicorn

 # Frontend

HTML5

CSS3

Vanilla JavaScript

Chart.js

React

TypeScript

Vite


## Setup & Installation
1: Clone the repository
git clone "https://github.com/norbzCk/sales_analysis.git"
cd sales-dashboard

2: Create a virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure environment variables
The backend now reads env vars:

- `DATABASE_URL` (required in production)
- `APP_SECRET_KEY` (required in production)
- `CORS_ORIGINS` (comma-separated list, recommended in production)

Example local values:
```bash
export DATABASE_URL='postgresql://postgres:postgres123@localhost:5432/sales_db'
export APP_SECRET_KEY='change-this-to-a-long-random-secret'
export CORS_ORIGINS='http://127.0.0.1:5500,http://localhost:5500'
```

### 5. Run backend
```bash
uvicorn backend.app.main:app --reload
```

Backend/API:
- `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

### 6. Choose frontend architecture

Legacy frontend:

### 6a. Configure legacy frontend API URL
Edit `frontend/js/config.js`:

```js
window.__APP_CONFIG__ = {
  API_BASE: "http://127.0.0.1:8000",
};
```

### 7a. Run legacy frontend
```bash
cd frontend
python -m http.server 5500


Then open:

http://127.0.0.1:5500/index.html

React + TypeScript frontend:

### 6b. Run the new frontend

```bash
cd frontend-react
npm install
npm run dev
```

Optional API override:

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

Then open:

`http://127.0.0.1:5173`

The React app is an architecture-first migration:

- It preserves the same product aim and backend API
- It centralizes routes, auth state, and HTTP access
- It creates dedicated feature boundaries for the remaining page migrations

## Deploy on Render

This repository is ready for a split Render deployment using the root `render.yaml`:

- `sales-analysis-api`: FastAPI web service
- `sales-db`: PostgreSQL database
- `sales-frontend`: React + Vite static site

### Render blueprint flow

1. Push this repository to GitHub.
2. In Render, create a new Blueprint and select the repo.
3. Render will detect `render.yaml` and provision the three resources.
4. Wait for `sales-db`, `sales-analysis-api`, and `sales-frontend` to finish provisioning.
5. Open the `sales-analysis-api` service and set `CORS_ORIGINS` to your frontend URL, such as `https://sales-frontend.onrender.com`.
6. If you previously created a manual Render web service for this repo, delete it or stop using it so future deploys come from the Blueprint-managed services instead.

### Important environment settings

The frontend static site is configured to call:

- `https://sales-analysis-api.onrender.com`

Before going live, set the backend `CORS_ORIGINS` value in Render to your frontend URL, for example:

```bash
https://sales-frontend.onrender.com
```

If you later rename the Render services or use a custom domain, update:

- `VITE_API_BASE` on the `sales-frontend` service
- `CORS_ORIGINS` on the `sales-analysis-api` service

### What the Blueprint config does

- Provisions a Render PostgreSQL database named `sales-db`
- Injects that database's private `connectionString` into `DATABASE_URL`
- Starts FastAPI with `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Builds the React frontend from `frontend-react` and publishes `dist`
- Adds an API health check at `/healthz`

### If your current Render service is failing

If your logs show a command like:

```bash
uvicorn backend.app.main:app --reload
```

or errors connecting to:

```bash
localhost:5432
```

then Render is using a manually created service instead of the Blueprint-managed setup. A fresh Blueprint deploy will fix that wiring.

### Notes

- The backend currently stores uploaded files on the service filesystem under `/uploads`. That works for simple deployments, but uploaded files may not be durable across redeploys or instance replacement. For production durability, move uploads to object storage.
- The frontend uses a single-page app rewrite to `/index.html`, so deep links like `/products` and `/orders` resolve correctly on Render.



