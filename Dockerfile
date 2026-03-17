# Use a specialized uv image for building
FROM ghcr.io/astral-sh/uv:python3.12-slim AS builder

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a multi-stage build
ENV UV_LINK_MODE=copy

WORKDIR /app

# Install the project's dependencies from the lockfile and pyproject.toml
# Note: We don't have a uv.lock yet, but uv can generate one or just use pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --frozen --no-install-project --no-dev

# Copy the source code
COPY . .

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Use a tiny run-time image
FROM python:3.12-slim

WORKDIR /app

# Copy the environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Ensure the app can find the project modules
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Expose the API port
EXPOSE 8000

# Run the service
CMD ["uvicorn", "maicro.main:app", "--host", "0.0.0.0", "--port", "8000"]
