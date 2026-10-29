"""
FastAPI wrapper around the RAG pipeline.

Run:    uvicorn src.api:app --reload
Then:   POST http://localhost:8000/ask  {"question": "..."}
Docs:   http://localhost:8000/docs
"""

import os
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.query import answer, get_collection

app = FastAPI(title="Regulatory Circular Assistant")

# a separate frontend (or a local dev server) calls the API from another
# origin; set CORS_ORIGINS="https://my-ui.example" to lock this down
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

Strategy = Literal[tuple(config.CHUNK_STRATEGIES)]
Mode = Literal[tuple(config.RETRIEVAL_MODES)]


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    strategy: Strategy = config.ACTIVE_CHUNK_STRATEGY
    mode: Mode = config.ACTIVE_RETRIEVAL_MODE
    top_k: int = Field(default=config.TOP_K, ge=1, le=10)


class SourceChunk(BaseModel):
    source: str
    chunk_index: int
    section: str
    score: float
    snippet: str
    text: str


class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceChunk]
    strategy: str
    mode: str


def collection_name(strategy: str) -> str:
    return f"{config.COLLECTION_NAME}_{strategy}"


def open_collection(strategy: str):
    try:
        return get_collection(collection_name(strategy))
    except Exception:
        raise HTTPException(503, f"Index for strategy '{strategy}' isn't built; "
                                 f"run: python src/ingest.py --strategy {strategy}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sources")
def sources(strategy: Strategy = config.ACTIVE_CHUNK_STRATEGY):
    """The documents in the index and how many chunks each has."""
    metadatas = open_collection(strategy).get(include=["metadatas"])["metadatas"]
    counts = {}
    for meta in metadatas:
        counts[meta["source"]] = counts.get(meta["source"], 0) + 1
    return {"strategy": strategy,
            "documents": [{"source": s, "chunks": n} for s, n in sorted(counts.items())]}


@app.post("/ask", response_model=AnswerResponse)
def ask(payload: Question):
    open_collection(payload.strategy)
    try:
        result = answer(payload.question, collection_name(payload.strategy),
                        k=payload.top_k, mode=payload.mode)
    except Exception as e:
        # retrieval is local, so a failure here is almost always the Groq call
        raise HTTPException(502, f"Answer generation failed: {type(e).__name__}: {e}")
    sources = [
        SourceChunk(
            source=meta["source"],
            chunk_index=meta["chunk_index"],
            section=meta.get("section", ""),
            score=score,
            snippet=chunk[:200],
            text=chunk,
        )
        for chunk, meta, score in result["retrieved"]
    ]
    return AnswerResponse(
        question=result["question"],
        answer=result["answer"],
        sources=sources,
        strategy=payload.strategy,
        mode=payload.mode,
    )
