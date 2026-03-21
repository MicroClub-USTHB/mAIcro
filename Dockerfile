FROM python:3.12-slim AS builder

RUN pip install uv

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src

RUN uv sync --frozen

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

COPY src ./src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]