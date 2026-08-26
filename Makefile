.PHONY: test bench check web web-smoke hosted-dev hosted-down migrate

test:
	uv run pytest

bench:
	uv run python -m mldsafail.benchmark.runner

check: test
	uv run python -m mldsafail.benchmark.runner --profile small --no-record

web:
	uv run python -m mldsafail.web.app

web-smoke:
	uv run python -c "from mldsafail.web.app import create_app; response = create_app().test_client().get('/'); assert response.status_code == 200; print('web smoke test passed')"

hosted-dev:
	docker compose --env-file deploy/dev.env -f compose.yaml -f compose.dev.yaml --profile build build
	docker compose --env-file deploy/dev.env -f compose.yaml -f compose.dev.yaml up -d db web proxy coordinator

hosted-down:
	docker compose --env-file deploy/dev.env -f compose.yaml -f compose.dev.yaml down

HOSTED_EVALUATOR_DIR ?= /Users/jarrett/dev/mldsafail-evaluator

hosted-setup:
	mkdir -p $(HOSTED_EVALUATOR_DIR)/secrets
	cp deploy/dev-hidden-seeds.json $(HOSTED_EVALUATOR_DIR)/secrets/hidden-seeds.json
	chmod 0400 $(HOSTED_EVALUATOR_DIR)/secrets/hidden-seeds.json

migrate:
	uv run alembic upgrade head
