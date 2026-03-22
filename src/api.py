"""FastAPI app — REST endpoint for the cooking agent pipeline."""

import time

import aiosqlite
from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

from src.config import settings
from src.metrics import REQUEST_LATENCY_SECONDS, REQUESTS_TOTAL
from src.services.pipeline import process_query

app = FastAPI(title="Cooking Agent API")


class QueryRequest(BaseModel):
    message: str
    chat_id: int = 0


class QueryResponse(BaseModel):
    response: str


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path != "/query":
        return await call_next(request)
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - t0
    result = "ok" if response.status_code < 500 else "error"
    REQUESTS_TOTAL.labels(channel="api", result=result).inc()
    REQUEST_LATENCY_SECONDS.labels(channel="api").observe(elapsed)
    return response


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    result = await process_query(req.message, req.chat_id)
    return QueryResponse(response=result)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/logs")
async def logs(limit: int = 50):
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT timestamp, chat_id, user_message, bot_response, feedback "
            "FROM logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]
