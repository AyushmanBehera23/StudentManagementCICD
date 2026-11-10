.PHONY: setup up down logs ps test lint fmt backup restore smoke drill release rollback clean

setup:            ## one-time: env file, secrets, TLS cert
	@test -f .env || cp .env.example .env
	scripts/gen-secrets.sh
	scripts/gen-certs.sh

up: setup         ## build and start the whole stack, wait until healthy
	docker compose up -d --build --wait

down:
	docker compose down

logs:
	docker compose logs -f --tail 100

ps:
	docker compose ps

test:             ## run API tests locally (sqlite)
	pytest

lint:
	ruff format --check . && ruff check . && bandit -q -r app

fmt:
	ruff format . && ruff check --fix .

backup:
	scripts/backup.sh

restore:          ## make restore FILE=backups/xxx.dump
	scripts/restore.sh $(FILE)

smoke:
	scripts/smoke.sh

drill:
	scripts/drill.sh

release:          ## make release VERSION=v1.0.1  (local build + gated deploy + auto rollback)
	LOCAL_BUILD=true scripts/deploy.sh $(VERSION)

rollback:
	scripts/rollback.sh $(TAG)

clean:            ## DESTROYS data volume
	docker compose down -v
