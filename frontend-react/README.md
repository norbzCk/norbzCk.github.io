# React Frontend Migration

This folder introduces a React + TypeScript frontend architecture for the existing sales platform without changing the backend goal or API surface.

## What changed

- Added a Vite-based React + TypeScript app
- Centralized routing with `react-router-dom`
- Added shared auth/session management
- Added a typed HTTP client for the existing FastAPI API
- Mapped current flows into React routes so features can be migrated incrementally

## Current scope

Implemented:

- Public home route
- Login and core registration flow
- Business registration
- Customer registration
- Logistics registration
- Initial admin dashboard metrics
- Products
- Orders
- Customers
- Providers
- Payments
- Profile
- Users
- Sales
- Logistics dashboard

## Run

1. Install frontend dependencies:

```bash
cd frontend-react
npm install
```

2. Start the React app:

```bash
npm run dev
```

3. If needed, point the frontend to a different backend:

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```


