.PHONY: dev dev-down test lint migrate shell logs keycloak-setup

dev:
	docker compose -f docker-compose.dev.yml up --build

dev-down:
	docker compose -f docker-compose.dev.yml down

dev-clean:
	docker compose -f docker-compose.dev.yml down -v

test:
	docker compose -f docker-compose.dev.yml exec backend pytest

lint:
	docker compose -f docker-compose.dev.yml exec backend ruff check .

migrate:
	docker compose -f docker-compose.dev.yml exec backend alembic upgrade head

shell:
	docker compose -f docker-compose.dev.yml exec backend bash

logs:
	docker compose -f docker-compose.dev.yml logs -f backend worker

keycloak-setup:
	./docker/keycloak/setup-realm.sh
