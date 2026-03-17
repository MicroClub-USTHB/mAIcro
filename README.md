# mAIcro: Open Source AI Service

## Quickstart

> **Prerequisites:** [Python 3.10+](https://python.org) and [uv](https://docs.astral.sh/uv/) installed.

#### 1. Clone & install dependencies

```bash
git clone https://github.com/MicroClub-USTHB/mAIcro.git
cd mAIcro
uv sync
```

#### 2. Set up your `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in the three required services:

| Variable | Where to get it |
|---|---|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) — create an API key |
| `DISCORD_BOT_TOKEN` | [Discord Developer Portal](https://discord.com/developers/applications) — create a bot, copy its token |
| `DISCORD_CHANNEL_IDS` | Right-click a Discord channel → *Copy Channel ID* (comma-separated for multiple) |
| `QDRANT_URL` | [Qdrant Cloud](https://cloud.qdrant.io) — create a free cluster (1 GB), copy the URL |
| `QDRANT_API_KEY` | Qdrant Cloud dashboard → *API Keys* → create a key |

#### 4. Run & Test

**Option A: Standard (local)**
```bash
uv run uvicorn maicro.main:app --host 0.0.0.0 --port 8000
```

**Option B: Docker (recommended)**
```bash
docker compose up -d
```

#### 5. Ingest & ask

```bash
# Trigger Discord ingestion (Stateless - cursors saved to Cloud)
curl -X POST http://localhost:8000/api/v1/ingest/discord

# Ask a question
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What projects are the dev team working on?"}'
```

---

## 🛠 Troubleshooting & Tips

### 1. Discord Bot permissions
If ingestion returns empty or 0 messages, check:
- **Intents:** Go to [Discord Developer Portal](https://discord.com/developers/applications) → Bot → **Message Content Intent** (must be ON).
- **Permissions:** The bot needs `View Channels` + `Read Message History` in the specific channels.
- **Bot Presence:** Ensure the bot is actually invited to the server.

### 2. Qdrant Cloud "400 Bad Request"
This project auto-creates **Payload Indexes**. If you get a 400 error about missing indexes, the server will attempt to fix it on startup. Ensure your QDRANT_API_KEY has "Manage" or "Admin" permissions.

### 3. Google Gemini Quota
If you get `429 Resource Exhausted`, you have hit the free tier rate limit. Wait 60 seconds and retry.

---

## 🤖 Discord Bot Setup Guide (Detailed)

1. Create an application at [Discord Developers](https://discord.com/developers/applications).
2. Go to the **Bot** tab:
   - Click "Reset Token" to get your `DISCORD_BOT_TOKEN`.
   - Scroll down to **Privileged Gateway Intents** → Enable **Message Content Intent**.
3. Go to **OAuth2** → **URL Generator**:
   - Scopes: `bot`.
   - Bot Permissions: `Read Messages/View Channels`, `Read Message History`.
   - Copy the generated URL and open it in your browser to invite the bot.
4. To get `DISCORD_CHANNEL_IDS`:
   - Enable "Developer Mode" in Discord Settings → Advanced.
   - Right-click any channel → **Copy Channel ID**.

---

> **Note:** This build is **Gemini-only** — set `LLM_PROVIDER=google` (the default).

## Contributing

Contributions are welcome — bug reports, docs improvements, and pull requests.

- Start here: `CONTRIBUTING.md`
- Security issues: `SECURITY.md`
- Quick dev loop:

```bash
cp .env.example .env          # fill in your credentials (see Quickstart above)
uv sync --dev
uv run pytest
uv run uvicorn maicro.main:app --reload
```

## Open-Source Release Checklist

To publish this project as true open source:

1. Add a `LICENSE` file (no license means others cannot legally reuse the code).
2. Keep secrets out of git: never commit `.env` (use `.env.example` instead).
3. Keep runtime state out of git: do not commit runtime state directories (for example `var/`).
4. Publish the repo (for example on GitHub) as public and accept contributions via PRs.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Health check |
| `/api/v1/ask` | POST | Ask a question (`{"question": "..."}`) |
| `/api/v1/ingest/discord` | POST | Trigger Discord ingestion |

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
├── src/
│   └── maicro/
│       ├── main.py        # Canonical FastAPI app entrypoint
│       ├── api/           # HTTP routes, schemas, error handlers
│       ├── core/          # Config, logging, ingestion, providers, vector store
│       └── services/      # Business logic (Q&A service)
├── data/                  # Legacy sample data (not used by default)
├── tests/
│   ├── api/               # API route tests
│   └── unit/              # Unit tests
├── var/                   # Runtime state (local vector DB path)
├── main.py                # Backward-compatible wrapper entrypoint
└── pyproject.toml         # Packaging and project metadata
```

For new setups, prefer `maicro.main:app`.

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
