# mAIcro: Open Source AI Service

## Setup (uv Only)

This project uses `uv` as the single dependency manager.

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Do not use `pip install -r requirements.txt`.

This build is **Gemini-only**: set `LLM_PROVIDER=google` and configure `GOOGLE_API_KEY`.

## CLI Usage

After `uv sync`, you can run:

```bash
uv run maicro-ask "When is the next event?"
uv run maicro-ingest
```

## Package Publishing Notes

This repository is structured for packaging from `pyproject.toml`.

```bash
uv build
```

## Overview

**mAIcro** is an open-source AI service designed to help organizations centralize information and answer questions based on their internal data.

It is not a simple chatbot or a Discord bot.
Instead, **mAIcro acts as an AI-powered knowledge service** that understands structured information and uses it to provide accurate answers to users.

The system can process organizational data such as announcements, documentation, and structured datasets, then make that information easily accessible through natural language queries.

While the first deployment of mAIcro is within **Micro Club**, the system itself is designed as **reusable infrastructure** that can be adapted to any community or organization.

# Goals

The main goals of **mAIcro** are:

* Centralize important information in one accessible system
* Allow members to query information using natural language
* Reduce repetitive questions asked to staff or moderators
* Provide reliable answers based on official sources
* Create reusable AI infrastructure for communities

---

# Project Structure

```text
.
├── app/
│   ├── main.py            # Canonical FastAPI app entrypoint
│   ├── cli.py             # CLI commands (ask, ingest)
│   ├── api/               # HTTP routes, schemas, error handlers
│   ├── core/              # Config, logging, ingestion, providers, vector store
│   └── services/          # Business logic (Q&A service)
├── data/                  # Local data sources used for ingestion
├── tests/                 # Unit and API tests
├── main.py                # Backward-compatible wrapper entrypoint
├── ask.py                 # Backward-compatible CLI wrapper
├── ingest.py              # Backward-compatible CLI wrapper
└── pyproject.toml         # Packaging and script entrypoints
```

For new setups, prefer `app.main:app` and the `maicro-*` CLI scripts.

---

# Core Concept

At its core, **mAIcro works as an AI service that understands provided data and answers questions based on it**.

Instead of relying on generic internet knowledge, the system operates on **specific datasets provided by the organization**.

These datasets may include:

* Official announcements
* Event information
* Internal documentation
* FAQs
* Structured data about activities or members

The AI processes this information and uses it to respond to user queries.

---

# Key Features

## Structured Data Understanding

mAIcro is designed to ingest and understand structured sources of information.
This allows it to reason about internal data rather than relying solely on general AI knowledge.

---

## Question Answering

Members can ask questions in natural language and receive answers derived directly from the organization's data.

Example questions:

* When is the next event?
* Where can I apply for the AI team?
* What are the rules for joining a workshop?

---

## Information Centralization

Organizations often have information scattered across multiple platforms:

* Discord
* Google Docs
* Notion
* Spreadsheets
* Announcements

mAIcro centralizes these sources into a **single AI-accessible knowledge system**.

---

## Adaptable Architecture

The system is designed so that it can be **adapted to different organizations** without rebuilding everything.

Possible use cases include:

* Student clubs
* Online communities
* Companies
* NGOs
* Developer communities

---

# Open Source Philosophy

mAIcro is released as an **open-source project**.

This means:

* Anyone can use the system
* Anyone can adapt it for their own community
* Anyone can contribute improvements

The goal is to build **shared AI infrastructure** that communities can deploy easily.

---

# First Deployment: Micro Club

The first deployment of mAIcro is within **Micro Club**.

In this environment, the system will:

* process official club announcements
* answer questions from members
* provide information about events, teams, and opportunities

However, **Micro Club is only the first use case**.
The architecture is designed to be reused by other communities.

---

# Future Extensions

mAIcro can evolve beyond a question-answering service.

Possible future features include:

### Agentic AI Features

The system may incorporate AI agents capable of:

* automating workflows
* summarizing announcements
* notifying members about relevant events
* managing knowledge updates

---

### Multi-Platform Integration

Future integrations may include:

* Discord
* Web dashboards
* APIs for other tools
* Knowledge management platforms
