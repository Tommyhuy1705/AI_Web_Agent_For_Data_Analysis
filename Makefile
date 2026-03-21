# ============================================================
# SIA — Makefile
# Shortcuts for common development and deployment tasks.
# Usage: make <target>
# ============================================================

.PHONY: help up down build logs test lint clean deploy pull

# Default target
help:
	@echo ""
	@echo "SIA — Sales Intelligence Agent"
	@echo "================================"
	@echo "Development:"
	@echo "  make up         Start all services (build if needed)"
	@echo "  make down       Stop all services"
	@echo "  make build      Rebuild Docker images"
	@echo "  make logs       Tail logs from all containers"
	@echo "  make logs-be    Tail backend logs only"
	@echo "  make logs-fe    Tail frontend logs only"
	@echo ""
	@echo "Testing:"
	@echo "  make test       Run backend unit tests"
	@echo "  make lint       Run Python linting (ruff)"
	@echo ""
	@echo "Database:"
	@echo "  make seed       Load mock data into database"
	@echo "  make migrate    Apply database migrations"
	@echo ""
	@echo "Production:"
	@echo "  make deploy     Pull latest images and restart (prod)"
	@echo "  make pull       Pull latest code from GitHub"
	@echo ""

# ── Development ──────────────────────────────────────────────

up:
	docker compose up --build -d
	@echo "✓ Services started. Backend: http://localhost:8000 | Frontend: http://localhost:3000"

down:
	docker compose down
	@echo "✓ Services stopped."

build:
	docker compose build --no-cache

logs:
	docker compose logs -f --tail=100

logs-be:
	docker compose logs -f --tail=100 backend

logs-fe:
	docker compose logs -f --tail=100 frontend

restart:
	docker compose restart

# ── Testing ──────────────────────────────────────────────────

test:
	@echo "Running backend tests..."
	cd backend && pip install pytest pytest-asyncio httpx -q && \
	pytest tests/ -v --tb=short

lint:
	@echo "Running linting..."
	pip install ruff -q && ruff check backend/ --fix

# ── Database ─────────────────────────────────────────────────

seed:
	@echo "Loading mock data..."
	python database/seed/mock_data_loader.py

migrate:
	@echo "Applying migrations..."
	@echo "Run: psql \$$SUPABASE_DATABASE_URL -f database/migrations/001_initial_schema.sql"
	@echo "Run: psql \$$SUPABASE_DATABASE_URL -f database/migrations/002_public_schema.sql"

# ── Production (AWS) ─────────────────────────────────────────

pull:
	git pull origin main
	@echo "✓ Latest code pulled from GitHub."

deploy:
	@echo "Deploying latest images from ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | \
	  docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker compose -f docker-compose.prod.yml pull
	docker compose -f docker-compose.prod.yml up -d --remove-orphans
	docker image prune -f
	@echo "✓ Deployment complete."

# ── Cleanup ──────────────────────────────────────────────────

clean:
	docker compose down -v --remove-orphans
	docker system prune -f
	@echo "✓ Cleaned up Docker resources."
