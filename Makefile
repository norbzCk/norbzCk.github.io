.PHONY: help build up down restart logs clean dev frontend backend

help:
	@echo "Commands:"
	@echo "  make build    - Build all Docker images"
	@echo "  make up       - Start all services via Docker"
	@echo "  make down     - Stop all services"
	@echo "  make restart  - Restart all services"
	@echo "  make logs     - View logs"
	@echo "  make clean    - Remove containers and volumes"
	@echo "  make dev      - Start backend + frontend locally (no Docker)"
	@echo "  make backend  - Start only the FastAPI backend locally"
	@echo "  make frontend - Start only the Vite frontend locally"

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
	/home/norbs-ck/sales_project/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

frontend:
	cd frontend-react && npm run dev -- --host 0.0.0.0