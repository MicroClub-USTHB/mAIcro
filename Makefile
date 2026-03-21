.PHONY: dev build prod stop clean test lint format logs shell help

# Default target
help:
	@echo "mAIcro Development CLI"
	@echo "----------------------"
	@echo "make dev    - Start the development stack with hot-reloading"
	@echo "make test   - Run the test suite inside the container"
	@echo "make lint   - Check code style with ruff"
	@echo "make format - Reformat code with ruff"
	@echo "make build  - Build the production Docker image"
	@echo "make prod   - Start the production stack"
	@echo "make stop   - Stop all project containers"
	@echo "make clean  - Reset environment (remove volumes and orphans)"
	@echo "make logs   - Stream logs from the application"
	@echo "make shell  - Open a shell inside the container"

# Start development stack
dev:
	docker compose -f docker-compose.dev.yml up --build -d

# Build production image
build:
	docker build -t maicro:latest .

# Start production stack
prod:
	docker compose up --build -d

# Stop the project
stop:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# Full clean reset
clean:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --rmi all --remove-orphans

# Run tests
test:
	docker compose exec maicro /app/.venv/bin/pytest

# Lint code
lint:
	docker compose exec maicro /app/.venv/bin/ruff check .

# Format code
format:
	docker compose exec maicro /app/.venv/bin/ruff format .

# View logs
logs:
	docker compose logs -f maicro

# Interactive shell
shell:
	docker compose exec maicro /bin/bash
