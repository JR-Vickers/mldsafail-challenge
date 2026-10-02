FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.8.11@sha256:8101ad825250a114e7bef89eefaa73c31e34e10ffbe5aff01562740bac97553c /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY examples/mlwe/primal-lll/solver.py ./examples/mlwe/primal-lll/solver.py
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
RUN groupadd --system --gid 10001 mldsafail && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent mldsafail
WORKDIR /app
COPY --from=builder --chown=mldsafail:mldsafail /build/.venv .venv
COPY --chown=mldsafail:mldsafail alembic.ini ./
COPY --chown=mldsafail:mldsafail migrations ./migrations
COPY --chown=mldsafail:mldsafail deploy/start-web.sh ./deploy/start-web.sh
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["./deploy/start-web.sh"]
