.PHONY: test bench check web

test:
	uv run pytest

bench:
	uv run python -m mldsafail.benchmark.runner

check: test
	uv run python -m mldsafail.benchmark.runner --profile toy-small

web:
	uv run python -m mldsafail.web.app
