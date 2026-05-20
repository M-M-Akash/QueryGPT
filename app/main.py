import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse  # pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles  # pyrefly: ignore [missing-import]

from app.config import settings
from app.database.schema import get_database_schema
from app.database.seed import seed_database
from app.pipeline.query_gpt import QueryGPT
from app.schemas import ExecuteRequest, PrepareRequest, PrepareResponse, QueryRequest, QueryResponse

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

pipeline: QueryGPT | None = None
_schema_info: dict = {}

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, _schema_info
    logger.info("Seeding database …")
    seed_database()
    logger.info("Loading schema …")
    _schema_info = get_database_schema()
    logger.info("Initialising QueryGPT pipeline …")
    pipeline = QueryGPT()
    logger.info("QueryGPT ready")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="QueryGPT",
    description="Natural Language to SQL conversion API",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/tables", summary="List all available tables")
async def list_tables():
    return {"tables": sorted(_schema_info.keys())}


@app.post("/query/prepare", response_model=PrepareResponse, summary="Detect intent and suggest tables")
async def prepare_query(request: PrepareRequest):
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised yet")
    try:
        result = pipeline.prepare_query(request.query)
        return result
    except Exception as exc:
        logger.exception("Error during query preparation")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query/execute", response_model=QueryResponse, summary="Execute with user-confirmed tables")
async def execute_query(request: ExecuteRequest):
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised yet")
    try:
        result = pipeline.execute_query(request.query, request.intent, request.confirmed_tables)
        return result
    except Exception as exc:
        logger.exception("Error during query execution")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query", response_model=QueryResponse)
async def generate_query(request: QueryRequest):
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised yet")
    try:
        result = pipeline.generate_query(request.query)
        return result
    except Exception as exc:
        logger.exception("Error processing query")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query/stream/execute", summary="Stream SQL tokens for pre-confirmed tables via SSE")
async def stream_execute_query(request: ExecuteRequest):
    """
    Server-Sent Events endpoint for the two-step flow.
    Accepts intent and confirmed tables from /query/prepare and streams SQL generation.

        data: {"event": "columns", "data": {...}}\n\n
        data: {"event": "samples", "data": [...]}\n\n
        data: {"event": "token",   "data": "<token>"}\n\n   ← one per LLM token
        data: {"event": "done",    "data": {}}\n\n
        data: {"event": "error",   "data": "<message>"}\n\n
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised yet")

    async def event_generator():
        async for event in pipeline.astream_execute(request.query, request.intent, request.confirmed_tables):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/query/stream", summary="Stream SQL generation tokens via SSE")
async def stream_query(request: QueryRequest):
    """
    Server-Sent Events endpoint.  Each event is a JSON line:

        data: {"event": "intent",  "data": {...}}\n\n
        data: {"event": "tables",  "data": [...]}\n\n
        data: {"event": "columns", "data": {...}}\n\n
        data: {"event": "samples", "data": [...]}\n\n
        data: {"event": "token",   "data": "<token>"}\n\n   ← one per LLM token
        data: {"event": "done",    "data": {}}\n\n
        data: {"event": "error",   "data": "<message>"}\n\n
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised yet")

    async def event_generator():
        async for event in pipeline.astream_query(request.query):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
