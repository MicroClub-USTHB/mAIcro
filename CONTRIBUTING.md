# Contributing

Thanks for your interest in contributing to **mAIcro**.

## Ways to help

- Report bugs (include steps to reproduce and expected vs actual behavior).
- Suggest features (include the problem you’re trying to solve and constraints).
- Improve docs (typos, examples, setup clarity).
- Send PRs (small, focused changes are easiest to review).

If you’ve found a security issue, please follow `SECURITY.md` instead of opening a public issue.

Start the local dev service:

```bash
uv sync --dev
cp .env.example .env
# Edit .env and set at least:
# API_KEY=...
# LLM_PROVIDER=google
# GEMINI_API_KEY=...
# QDRANT_URL=http://localhost:6333
```

## Common commands

Run tests:

```bash
uv run pytest
```

Start the API locally:

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Pull requests

- Keep PRs focused and small when possible.
- Include tests for behavior changes and bug fixes.
- Update `README.md` / docs for user-facing changes.
- Don’t commit secrets (keep `.env` local; update `.env.example` if you add a new setting).
- Don’t commit local state directories (for example `var/` or `local_qdrant/`).

## Reporting issues

Use GitHub Issues for bugs and feature requests.
