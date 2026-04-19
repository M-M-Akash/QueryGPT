# QueryGPT

A natural language to SQL pipeline powered by a chain of LLM agents, RAG-based few-shot learning, and a Neo4j vector store. Ask questions in plain English and get back executable SQL — with full intermediate reasoning exposed.

---

## How It Works

A user query passes through four sequential agents before SQL is generated and executed:

```
User Query
    │
    ▼
┌──────────────┐
│ IntentAgent  │  Classifies the query intent and target workspace
└──────┬───────┘
       ▼
┌──────────────┐
│  TableAgent  │  Selects only the relevant tables from the schema
└──────┬───────┘
       ▼
┌──────────────────┐
│ ColumnPruneAgent │  Prunes columns that are irrelevant to the query
└──────┬───────────┘
       ▼
┌──────────────┐
│ SQLGenerator │  Generates SQL using the LLM + RAG few-shot examples
└──────┬───────┘
       ▼
   Execute & Return results
```

Each agent narrows the context handed to the next, keeping prompts focused and improving SQL accuracy.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| LLM inference | Ollama (local, e.g. `llama3.2`) |
| Embeddings | Ollama (`nomic-embed-text`) via LangChain |
| Vector store | Neo4j (LlamaIndex integration) |
| Database | SQLite |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
app/
├── main.py                # FastAPI app and startup lifespan
├── config.py              # Pydantic settings (loaded from .env)
├── schemas.py             # Request / response models
├── agents/
│   ├── intent.py          # IntentAgent
│   ├── table.py           # TableAgent
│   ├── column_prune.py    # ColumnPruneAgent
│   └── sql_generator.py   # SQLGenerator with RAG retrieval
├── database/
│   ├── connection.py      # SQLite connection context manager
│   ├── schema.py          # Schema introspection helpers
│   ├── seed.py            # Sample data seeding on startup
│   └── samples.py         # Few-shot example queries
├── pipeline/
│   └── query_gpt.py       # Pipeline orchestrator
├── utils/
│   └── formatting.py      # Output formatting helpers
└── vectorstore/
    └── store.py           # Neo4j vector store + embedding indexing
```

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- No GPU required — Ollama runs on CPU by default

### 1. Clone the repository

```bash
git clone https://github.com/your-username/QueryGPT.git
cd QueryGPT
```

### 2. Configure environment variables

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `OLLAMA_HOST` | Ollama server URL, e.g. `http://ollama:11434` |
| `OLLAMA_MODEL` | LLM model name, e.g. `llama3.2` |
| `OLLAMA_EMBED_MODEL` | Embedding model, e.g. `nomic-embed-text` |
| `NEO4J_URL` | Neo4j Bolt URL, e.g. `bolt://neo4j:7687` |
| `NEO4J_USERNAME` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `NEO4J_EMBEDDING_DIMENSION` | Dimension of the embedding model (e.g. `768`) |
| `DATABASE_PATH` | Path to the SQLite file, e.g. `/data/querygpt.db` |
| `LOG_LEVEL` | Optional. `INFO` by default |
| `SIMILARITY_TOP_K` | Optional. Number of RAG examples to retrieve. `2` by default |

### 3. Start all services

```bash
docker compose up --build
```

This will:
- Start an Ollama server and pull `llama3.2` and `nomic-embed-text`
- Start a Neo4j instance
- Build and start the QueryGPT API

The API will be available at `http://localhost:8000`.

> **GPU support:** To enable NVIDIA GPU acceleration for Ollama, uncomment the `deploy.resources` block in `docker-compose.yml`.

---

## API Usage

### Health check

```
GET /health
```

```json
{ "status": "ok" }
```

### Generate SQL from natural language

```
POST /query
Content-Type: application/json
```

**Request body:**

```json
{
  "query": "Show me the top 5 customers by total order value"
}
```

**Response:**

```json
{
  "user_query": "Show me the top 5 customers by total order value",
  "intent": { ... },
  "tables": { ... },
  "pruned_schema": { ... },
  "similar_samples": [ ... ],
  "sql_result": { ... },
  "execution_success": true,
  "query_result": [ ... ],
  "execution_error": null
}
```

Interactive docs are available at `http://localhost:8000/docs`.

---

## Running Locally (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Make sure Ollama and Neo4j are running and .env is configured
uvicorn app.main:app --reload
```
└── utils/
    └── formatting.py       # LLM output parsing
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- NVIDIA GPU + drivers (for Ollama GPU acceleration; CPU-only works too)

### Run

```bash
# 1. Copy and adjust environment variables
cp .env.example .env

# 2. Start all services
docker compose up --build -d

# 3. Wait for the ollama-pull service to finish downloading models
docker compose logs -f ollama-pull

# 4. The API is available at http://localhost:8000
```

### API Usage

```bash
# Health check
curl http://localhost:8000/health

# Generate SQL from natural language
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me all customers from New York who made purchases above $500"}'
```

### API Docs

Interactive documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configuration

All settings are configured via environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | LLM model for agents |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `NEO4J_URL` | `bolt://neo4j:7687` | Neo4j connection URL |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `password123` | Neo4j password |
| `DATABASE_PATH` | `/data/retail.db` | SQLite database path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SIMILARITY_TOP_K` | `2` | Number of similar examples for RAG |

## Development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Point to local services
export OLLAMA_HOST=http://localhost:11434
export NEO4J_URL=bolt://localhost:7687
export DATABASE_PATH=./retail.db

uvicorn app.main:app --reload
```
