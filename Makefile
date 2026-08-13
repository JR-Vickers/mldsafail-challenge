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
	docker compose --env-file deploy/dev.env -f compose.yaml -f compose.dev.yaml up -d db web proxy

hosted-down:
	docker compose --env-file deploy/dev.env -f compose.yaml -f compose.dev.yaml down

migrate:
	uv run alembic upgrade head
