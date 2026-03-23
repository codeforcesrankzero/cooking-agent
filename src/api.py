"""FastAPI app — REST endpoint for the cooking agent pipeline."""

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response
from pydantic import BaseModel

from src.services.pipeline import process_query

app = FastAPI(title="Cooking Agent API")


class QueryRequest(BaseModel):
    message: str
    chat_id: int = 0


class QueryResponse(BaseModel):
    response: str


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
