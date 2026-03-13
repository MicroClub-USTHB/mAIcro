# Contributing

Thanks for your interest in contributing to **mAIcro**.

## Ways to help

- Report bugs (include steps to reproduce and expected vs actual behavior).
- Suggest features (include the problem you’re trying to solve and constraints).
- Improve docs (typos, examples, setup clarity).
- Send PRs (small, focused changes are easiest to review).

If you’ve found a security issue, please follow `SECURITY.md` instead of opening a public issue.

## Development setup

### Prerequisites

- Python 3.10+ (CI runs 3.10–3.12)
- `uv` (dependency management + runner)
- Docker (recommended) to run Qdrant locally

### Install + configure

```bash
cp .env.example .env
uv sync --dev
```

Start Qdrant (required for running the service locally):

```bash
docker run --rm -p 6333:6333 qdrant/qdrant
```

Edit `.env` and set at least:

- `LLM_PROVIDER=google`
- `GOOGLE_API_KEY=...`
- `QDRANT_URL=http://localhost:6333`

## Common commands

Run tests:

```bash
uv run pytest
```

Start the API locally:

```bash
uv run uvicorn maicro.main:app --reload
```

CLI wrappers (optional):

```bash
uv run python ask.py "When is the next event?"
uv run python ingest.py --limit 200
```

## Pull requests

- Keep PRs focused and small when possible.
- Include tests for behavior changes and bug fixes.
- Update `README.md` / docs for user-facing changes.
- Don’t commit secrets (keep `.env` local; update `.env.example` if you add a new setting).
- Don’t commit local state directories (for example `var/` or `local_qdrant/`).

## Reporting issues

Use GitHub Issues for bugs and feature requests.
