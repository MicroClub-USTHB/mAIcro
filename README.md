# mAIcro: Community Intelligence Service

mAIcro is a reusable, open-source AI infrastructure designed for communities and organizations. It understands structured data, processes official announcements, and answers questions accurately by centralizing important information.

## Vision

- **Community-First**: Built for MicroClub-USTHB, but designed for everyone.
- **Reusable**: Adaptable to any organization with minimal config.
- **Intelligent**: Leveraging RAG (Retrieval-Augmented Generation) and Agentic features.

## Tech Stack

- **Backend**: FastAPI
- **AI**: Gemini / LangChain
- **Database**: ChromaDB
- **Environment Management**: Poetry

## Project Structure

- `app/api/`: API endpoints.
- `app/core/`: Configuration and settings.
- `app/services/ai/`: Core AI logic.
- `app/services/knowledge/`: Knowledge base management.
- `app/services/ingestors/`: Data processing logic.

## Getting Started

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in your keys.
3. Install dependencies: `poetry install`.
4. Run the app: `uvicorn app.main:app --reload`.

## Observability

- Tracing dashboard setup and usage: `docs/tracing-dashboard.md`
- Prometheus metrics endpoint: `GET /metrics`
