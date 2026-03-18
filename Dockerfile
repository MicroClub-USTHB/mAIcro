FROM ghcr.io/astral-sh/uv:0.10.11-python3.12-trixie AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-project --no-dev

COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

COPY src ./src

EXPOSE 8000

CMD ["uvicorn", "maicro.main:app", "--host", "0.0.0.0", "--port", "8000"]
