# Contributing to mAIcro

Thank you for your interest in contributing to mAIcro. This document sets the technical and cultural standards for contributions to ensure the project remains high-quality, reliable, and aligned with its core architecture.

## Project Philosophy

mAIcro is designed as a focused, high-performance RAG (Retrieval-Augmented Generation) service for organizations. Every contribution must respect these foundational principles:

*   **Simple and Clear** We favor straightforward implementations over complex abstractions. The codebase should be navigable without deep knowledge of specialized frameworks.
*   **Controlled Deployments** mAIcro is built for trusted environments (e.g., behind a Discord bot). It is not intended for use as a multi-tenant public API.
*   **Performance is a Feature** Every new abstraction or feature should be evaluated for its impact on performance and operational reliability.

## Ways to Contribute

*   **Bug Reports** Report verified bugs via GitHub Issues with clear reproduction steps, logs, and environment details.
*   **Feature Suggestions**: Propose new capabilities that align with the project's stateless philosophy. Open an issue for discussion before implementing.
*   **Documentation**: Improve clarity in READMEs, docstrings, or deployment guides.
*   **Pull Requests**: Submit code changes for verified bugs or approved features.

## What NOT to Contribute

To maintain a clean scope and architectural integrity, we will not accept contributions that introduce:

*   **Built-in Authentication**: Authentication must be handled at the deployment, proxy, or client level (e.g., Discord bot permissions). We explicitly reject custom user databases, password systems, or OAuth integrations within the core service.
*   **Public API Assumptions**: Features that assume the service is directly exposed to the open internet (e.g., browser-based session management without an intermediate application layer).
*   **Implicit State**: Global caches, local file-system dependencies, or in-memory state that cannot be replaced by external providers.

## Local Development

mAIcro uses a single **Docker Compose** configuration for local development. We provide a **Makefile** to simplify common commands.

### Prerequisites

*   [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
*   **Google Gemini API Key**: Required for LLM generation.
*   **Qdrant URL & API Key**: Required for vector search.

### Setup

1.  Initialize your environment:
    ```bash
    cp .env.example .env
    ```

2.  Set required variables in `.env`:
    *   `GEMINI_API_KEY`: Your Google AI Studio API key.

3.  Launch the development stack:
    ```bash
    make dev
    ```

The API will be available at `http://localhost:8000`. Documentation and interactive API testing are provided at `http://localhost:8000/api/v1/docs`. 

Hot-reloading is enabled through volume mapping, so code changes will automatically update the running service.

## Testing

We expect all logic changes to be covered by tests. All tests are run within the Docker environment to ensure accurate behavior.

```bash
make test
```

## Common Commands

*   `make dev` - Start the project in the background with hot-reloading.
*   `make test` - Run the test suite reliably inside the container.
*   `make lint` - Check code style and common errors using `ruff`.
*   `make format` - Automatically reformat code to match project standards.
*   `make build` - Build the production Docker image locally.
*   `make stop` - Stop all project containers.
*   `make clean` - Reset environment (remove volumes, images, and orphans).
*   `make logs` - Stream output from the application container.
*   `make shell` - Open a terminal inside the running application container.

## Pull Request Process

1.  **Branching**: Create a feature branch from `main` using descriptive names and send pull request to `dev` (e.g., `feature/hybrid-search`).
2.  **Atomic Commits**: Ensure each commit represents a single logical change.
3.  **Documentation**: Update relevant documentation if the change affects usage or architecture.
4.  **Review Cycle**: All PRs require at least one maintainer review. Be prepared to iterate on feedback.


## Security

If you discover a security vulnerability, do NOT open a public issue. Follow the process outlined in [SECURITY.md](SECURITY.md) for private disclosure.

## Issue Reporting

When opening an issue:
1.  Be descriptive and objective.
2.  For feature requests, explain why the feature belongs in the core stateless backend rather than a client-side implementation.
