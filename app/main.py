import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.config import settings
from app.database.seed import seed_database
from app.pipeline.query_gpt import QueryGPT
from app.schemas import QueryRequest, QueryResponse

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

pipeline: QueryGPT | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    logger.info("Seeding database …")
    seed_database()
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


@app.get("/health")
async def health():
    return {"status": "ok"}


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
