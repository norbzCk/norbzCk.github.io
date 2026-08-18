.PHONY: help build up down restart logs clean dev frontend backend supabase-push supabase-pull supabase-migrate supabase-schema

VENV = /home/norbs-ck/sales_project/venv/bin

help:
	@echo "Commands:"
	@echo "  make build            - Build all Docker images"
	@echo "  make up               - Start all services via Docker"
	@echo "  make down             - Stop all services"
	@echo "  make restart          - Restart all services"
	@echo "  make logs             - View logs"
	@echo "  make clean            - Remove containers and volumes"
	@echo "  make dev              - Start backend + frontend locally (no Docker)"
	@echo "  make backend          - Start only the FastAPI backend locally"
	@echo "  make frontend         - Start only the Vite frontend locally"
	@echo "  make supabase-schema  - Export SQL schema for Supabase"
	@echo "  make supabase-push    - Sync local DB -> Supabase"
	@echo "  make supabase-pull    - Sync Supabase -> local DB"
	@echo "  make supabase-migrate - Run Alembic migrations against Supabase"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

clean:
	docker compose down -v

dev: backend frontend

backend:
	$(VENV)/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

frontend:
	cd frontend-react && npm run dev -- --host 0.0.0.0

supabase-push:
	$(VENV)/python -m backend.supabase_sync push

supabase-pull:
	$(VENV)/python -m backend.supabase_sync pull

supabase-migrate:
	$(VENV)/alembic upgrade head

supabase-schema:
	$(VENV)/python -m backend.generate_sql_schema supabase_schema.sql