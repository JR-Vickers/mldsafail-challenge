.PHONY: test bench check web web-smoke

test:
	uv run pytest

bench:
	uv run python -m mldsafail.benchmark.runner

check: test
	uv run python -m mldsafail.benchmark.runner --profile toy-small --no-record

web:
	uv run python -m mldsafail.web.app

web-smoke:
	uv run python -c "from mldsafail.web.app import create_app; response = create_app().test_client().get('/'); assert response.status_code == 200; print('web smoke test passed')"
