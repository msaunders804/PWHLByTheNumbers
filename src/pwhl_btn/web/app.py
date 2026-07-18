"""
app.py — FastAPI web interface for the BTN PWHL Natural Language Query Engine.

Start locally:
    PYTHONPATH=src uvicorn pwhl_btn.web.app:app --reload --port 8000

On Railway, the Procfile handles startup automatically.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
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

# ── Rate limiting ─────────────────────────────────────────────────────────────
# 8 queries per IP per 60 seconds — enough for genuine exploration, blocks abuse.
_RATE_LIMIT  = 8
_RATE_WINDOW = 60  # seconds
_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    """Returns True if the IP is within the rate limit, False if exceeded."""
    now = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < _RATE_WINDOW]
    if len(_rate_store[ip]) >= _RATE_LIMIT:
        return False
    _rate_store[ip].append(now)
    return True

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
async def query(req: QueryRequest, request: Request):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit reached — max {_RATE_LIMIT} queries per minute. Try again shortly.",
        )
    # run_query is synchronous (DB + Claude calls) — offload to thread pool
    result = await asyncio.to_thread(run_query, req.question.strip())
    return JSONResponse(content=result)
