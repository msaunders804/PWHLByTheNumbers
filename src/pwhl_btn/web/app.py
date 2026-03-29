"""
app.py — FastAPI web interface for the BTN PWHL Natural Language Query Engine.

Start locally:
    PYTHONPATH=src uvicorn pwhl_btn.web.app:app --reload --port 8000

On Railway, the Procfile handles startup automatically.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from pwhl_btn.nlp.query_engine import run_query

app = FastAPI(title="BTN Query Engine", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_INDEX = Path(__file__).parent / "index.html"


class QueryRequest(BaseModel):
    question: str


@app.get("/")
async def root():
    return FileResponse(_INDEX)


@app.get("/health")
async def health():
    """Railway uses this to verify the service is alive."""
    return {"status": "ok"}


@app.post("/api/query")
async def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    # run_query is synchronous (DB + Claude calls) — offload to thread pool
    result = await asyncio.to_thread(run_query, req.question.strip())
    return JSONResponse(content=result)
