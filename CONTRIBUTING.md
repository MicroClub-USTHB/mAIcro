# Contributing

Thanks for your interest in contributing to **mAIcro**.

## Development setup

This repo uses `uv` for dependency management.

```bash
uv sync --dev
```

Run tests:

```bash
uv run pytest
```

Start the API locally:

```bash
uv run uvicorn maicro.main:app --reload
```

## Pull requests

- Keep PRs focused and small when possible.
- Include tests for behavior changes and bug fixes.
- Update `README.md` if you change user-facing behavior.

## Reporting issues

Use GitHub Issues for bugs and feature requests.

